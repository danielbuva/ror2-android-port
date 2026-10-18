// Subsystem: world/director (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup SelectStageCombatDeck, RecordStageCombatSpawn; teardown CleanupStageCombatDecks.
using System;
using System.Collections.Generic;
using System.Linq;
using RoR2;
using UnityEngine;

// Original native stage pools in whole-catalog mode; legacy filtered decks remain a rollback path.
// Card/category weights, availability and placement fields remain original; excluded content is explicit.
public sealed partial class PortSession
{
    [Serializable]
    public class StageCombatDeckSpec
    {
        public string name, asset;
        public int cards, categories, excluded;
    }
    [Serializable]
    public class StageCombatSpawn
    {
        public string card, director, master, body;
        public int count, directorInstanceId, spawnCardInstanceId;
        public bool inheritedWave;
    }
    [Serializable]
    public class StageCombatDeckReport
    {
        public string stage;
        public string[] cards;
        public int excluded;
        public bool nativePool, nativeScenePopulation, sourceSceneDirector, sourceGameManager;
        public int sourceContinuousDirectors, initialInteractableCredits, remainingInteractableCredits, playerSpawnPoints, droneDefinitions,
            availableDrones, pickupDefinitions, lunarLoot;
        public List<string> placedInteractables = new List<string>();
        public string[] interactableCards;
        public List<StageCombatSpawn> spawned = new List<StageCombatSpawn>();
    }
    readonly HashSet<CharacterMaster> stageCombatActors = new HashSet<CharacterMaster>();
    StageCombatDeckReport currentStageCombatDeck;
    sealed class InheritedStageWave
    {
        public DirectorCard selected;
        public CharacterSpawnCard spawnCard;
        public GameObject master, body;
    }
    readonly Dictionary<CombatDirector, InheritedStageWave> inheritedStageWaves = new Dictionary<CombatDirector, InheritedStageWave>();
    static DirectorCard SelectedStageCard(CombatDirector director)
    {
        return director
                   ? (DirectorCard) typeof(CombatDirector)
                         .GetField("currentMonsterCard", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)
                         .GetValue(director)
                   : null;
    }
    static bool ContainsStageCard(DirectorCardCategorySelection deck, DirectorCard card)
    {
        return deck && card != null && deck.categories.SelectMany(category => category.cards).Any(value => ReferenceEquals(value, card));
    }
    void RetainInheritedStageWave(CombatDirector director, DirectorCardCategorySelection previousDeck, DirectorCard previousCard,
                                  DirectorCardCategorySelection nextDeck)
    {
        if (!director || previousCard == null || ContainsStageCard(nextDeck, previousCard))
            return;
        Check(ContainsStageCard(previousDeck, previousCard), "In-flight director card does not belong to its previous owned deck");
        var source = previousCard.GetSpawnCard() as CharacterSpawnCard;
        var master = source && source.prefab ? source.prefab.GetComponent<CharacterMaster>() : null;
        Check(source && master && master.bodyPrefab, "In-flight director card has no original master/body contract");
        Check(nextDeck.categories.SelectMany(category => category.cards)
                  .Select(card => card.GetSpawnCard() as CharacterSpawnCard)
                  .Any(card => card && card.name == source.name && card.prefab == source.prefab &&
                               card.prefab.GetComponent<CharacterMaster>().bodyPrefab == master.bodyPrefab),
              "In-flight director wave has no matching original stage entry");
        inheritedStageWaves.Add(director, new InheritedStageWave { selected = previousCard, spawnCard = source, master = source.prefab,
                                                                   body = master.bodyPrefab });
    }

    void SelectStageCombatDeck(SessionConfig cfg, string stage)
    {
        if (cfg.stageCombatDecks == null || cfg.stageCombatDecks.Length == 0 || stage == "moon2")
            return;
        var spec = cfg.stageCombatDecks.SingleOrDefault(x => x.name == stage);
        Check(spec != null, "Recovered stage combat deck absent: " + stage);
        inheritedStageWaves.Clear();
        if (r.liveCatalogs != null)
        {
            // Replacing monsterCards updates future selection but preserves the native
            // current wave. Keep its exact owned card until this director selects another.
            var previousDirector = rewardDirector;
            var previousCard = SelectedStageCard(previousDirector);
            var previousDeck = previousDirector ? previousDirector.monsterCards : null;
            var native = SelectWholeStagePool(stage);
            var nativeCards = native.categories.SelectMany(category => category.cards).ToArray();
            RetainInheritedStageWave(previousDirector, previousDeck, previousCard, native);
            if (automaticDeck)
                Destroy(automaticDeck);
            automaticDeck = native;
            r.director.scope =
                "Original ClassicStageInfo/DccsPool/DCCSBlender population selection and native card availability; complete owned actor catalog. Android scene transport/input/audio boundaries remain; registration is not all-content behavior acceptance.";
            currentStageCombatDeck = new StageCombatDeckReport {
                stage = stage, cards = nativeCards.Select(card => card.GetSpawnCard().name).ToArray(), excluded = 0, nativePool = true,
                interactableCards = wholeStageInfo.interactableCategories
                                        ? wholeStageInfo.interactableCategories.categories.SelectMany(category => category.cards)
                                              .Select(card => card.GetSpawnCard().name)
                                              .ToArray()
                                        : new string[0]
            };
            r.director.stageDecks.Add(currentStageCombatDeck);
            if (rewardDirector)
                rewardDirector.monsterCards = native;
            if (sourceSlowDirector)
            {
                sourceSlowDirector.monsterCards = native;
                if (!sourceSlowDirector.enabled)
                    sourceSlowDirector.enabled = true;
            }
            return;
        }
        var source = artifactBundle.LoadAsset<DirectorCardCategorySelection>(spec.asset);
        Check(source && source.categories.Length == spec.categories, "Stage deck source categories differ");
        var deck = Instantiate(source);
        var cards = deck.categories.SelectMany(x => x.cards).ToArray();
        Check(cards.Length == spec.cards && cards.Length > 0, "Stage deck supported card count differs");
        var supported = new[] { rewardCard }.Concat(objectiveCards).ToDictionary(x => x.name, x => x);
        foreach (var card in cards)
        {
            CharacterSpawnCard owned;
            Check(card.spawnCard && supported.TryGetValue(card.spawnCard.name, out owned), "Stage deck references unavailable actor");
            card.spawnCard = supported[card.spawnCard.name];
            Check(card.selectionWeight > 0 && !card.requiredUnlockableDef && !card.forbiddenUnlockableDef &&
                      string.IsNullOrEmpty(card.requiredUnlockable) && string.IsNullOrEmpty(card.forbiddenUnlockable),
                  "Stage card profile restriction unavailable");
        }
        if (automaticDeck)
            Destroy(automaticDeck);
        automaticDeck = deck;
        r.director.scope =
            "Original continuous director/credits/targeting with supported source base-stage category/card contracts; inherited startup Beetle, incomplete actors/DLC/family pools/SceneDirector/platform context. Actual population recorded per stage; catalog registration is not actor acceptance.";
        currentStageCombatDeck =
            new StageCombatDeckReport { stage = stage, cards = cards.Select(x => x.spawnCard.name).ToArray(), excluded = spec.excluded };
        r.director.stageDecks.Add(currentStageCombatDeck);
        if (rewardDirector)
            rewardDirector.monsterCards = deck;
    }
    void RecordStageCombatSpawn(GameObject obj, CharacterBody player, CombatDirector director)
    {
        var master = obj.GetComponent<CharacterMaster>();
        Check(master && director && currentStageCombatDeck != null, "Stage combat spawn has no owned director/deck context");
        // The event owner identifies the emitting director, including the teleporter's
        // bonus population. The global primary director is not a proxy for this source.
        var candidates = (currentStageCombatDeck.nativePool ? wholeSpawnCards.Values : new[] { rewardCard }.Concat(objectiveCards))
                             .Where(card => currentStageCombatDeck.cards.Contains(card.name) &&
                                            card.prefab.GetComponent<CharacterMaster>().bodyPrefab == master.bodyPrefab)
                             .ToArray();
        var chosen = currentStageCombatDeck.nativePool ? SelectedStageCard(director) : null;
        InheritedStageWave retained;
        bool inherited = false;
        if (inheritedStageWaves.TryGetValue(director, out retained))
        {
            inherited = ReferenceEquals(chosen, retained.selected);
            if (!inherited)
                inheritedStageWaves.Remove(director);
        }
        var card = currentStageCombatDeck.nativePool ? (chosen != null ? chosen.GetSpawnCard() as CharacterSpawnCard : null)
                                                     : candidates.SingleOrDefault();
        if (inherited)
            Check(card == retained.spawnCard && card.prefab == retained.master && master.bodyPrefab == retained.body,
                  "Retained director wave changed its measured card/master/body identity");
        if (currentStageCombatDeck.nativePool)
        {
            Check(chosen != null && card && card.prefab && card.prefab.GetComponent<CharacterMaster>().bodyPrefab == master.bodyPrefab,
                  "Native director spawn body differs from its actual selected card");
            Check(inherited || ContainsStageCard(director.monsterCards, chosen),
                  "Native selected card is outside its emitting director's deck");
            Check(inherited || candidates.Contains(card), "Native director spawn does not match its actual selected card");
        }
        else
            Check(card && candidates.Contains(card), "Legacy director spawn does not match its supported actor");
        Check(card && currentStageCombatDeck.cards.Contains(card.name), "Native stage director spawned outside its supported deck");
        int directorId = director.GetInstanceID(), cardId = card.GetInstanceID();
        var row = currentStageCombatDeck.spawned.FirstOrDefault(x => x.directorInstanceId == directorId &&
                                                                     x.spawnCardInstanceId == cardId && x.inheritedWave == inherited);
        if (row == null)
        {
            row = new StageCombatSpawn {
                card = card.name,          director = director.name,      directorInstanceId = directorId, spawnCardInstanceId = cardId,
                master = card.prefab.name, body = master.bodyPrefab.name, inheritedWave = inherited
            };
            currentStageCombatDeck.spawned.Add(row);
        }
        row.count++;
        if (IsObjectiveActor(master.GetBody()))
        {
            stageCombatActors.Add(master);
            return;
        }
        RecordDirectorActor(obj, player);
    }
    void CleanupStageCombatDecks()
    {
        stageCombatActors.Clear();
        inheritedStageWaves.Clear();
        currentStageCombatDeck = null;
    }
}
