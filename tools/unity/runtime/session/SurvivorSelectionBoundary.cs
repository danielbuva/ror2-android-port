// Subsystem: session (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup SelectedPlayerPrefab, OrdinarySurvivorChoices; teardown —.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RoR2;
using UnityEngine;

// Ordinary selection follows the original survivor contract and the owned
// Android profile. Developer-only selections remain assisted.
public sealed partial class PortSession
{
    [Serializable]
    public class SourceAnimationEventReport
    {
        public string model;
        public float seconds;
        public bool componentEnabled, modelActive, characterBodyMatched, locatorPresent, cachedLocator, cachedBody;
        public bool[] airstrikeMuzzles;
    }
    float nextSourceAnimationObservation;
    GameObject selectedBodyStaging;
    HashSet<string> offlineUnlockPreview;
    void EnsureOfflineUnlockPreview()
    {
        if (offlineUnlockPreview == null)
            offlineUnlockPreview =
                AndroidOfflineProfile.PreviewUnlockNames(System.IO.Path.Combine(Application.persistentDataPath, "android-profile-v1"));
    }
    static string SurvivorUnlockName(SurvivorDef survivor)
    {
        return survivor.unlockableDef ? survivor.unlockableDef.cachedName : survivor.unlockableName;
    }
    SurvivorDef[] VisibleSurvivorRoster()
    {
        var definitions =
            WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef, Array.Empty<SurvivorDef>());
        var roster = definitions.Where(value => value && value.bodyPrefab && !value.hidden)
                         .OrderBy(value => value.desiredSortPosition)
                         .ThenBy(value => value.cachedName, StringComparer.Ordinal)
                         .ToArray();
        Check(roster.Length > 0 && roster.Select(value => value.cachedName).Distinct(StringComparer.Ordinal).Count() == roster.Length,
              "Original visible survivor roster changed");
        return roster;
    }
    bool IsOrdinarySurvivorAvailable(SurvivorDef survivor)
    {
        if (!survivor || !survivor.bodyPrefab || survivor.hidden || survivor.GetRequiredExpansion() || survivor.GetRequiredEntitlement())
            return false;
        var name = SurvivorUnlockName(survivor);
        if (string.IsNullOrEmpty(name))
            return true;
        EnsureOfflineUnlockPreview();
        return offlineUnlockPreview.Contains(name);
    }
    SurvivorDef[] OrdinarySurvivorChoices()
    {
        EnsureOfflineUnlockPreview();
        var definitions =
            WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef, Array.Empty<SurvivorDef>());
        var choices = definitions.Where(IsOrdinarySurvivorAvailable)
                          .OrderBy(value => value.cachedName == "Commando"   ? 0
                                            : value.cachedName == "Huntress" ? 1
                                                                             : 2)
                          .ThenBy(value => value.cachedName, StringComparer.Ordinal)
                          .ToArray();
        Check(choices.Any(value => value.cachedName == "Commando") && choices.Any(value => value.cachedName == "Huntress"),
              "Original free survivor choices unavailable");
        return choices;
    }
    void CycleOrdinarySurvivor(int direction)
    {
        var choices = offlineMenuChoices ?? OrdinarySurvivorChoices();
        var index = Array.FindIndex(choices, value => value.cachedName == r.selectedSurvivor);
        r.selectedSurvivor = choices[(index + direction + choices.Length) % choices.Length].cachedName;
        Save();
        if (offlineStartVisible)
            ResetOfflineLoadoutSelection();
    }
    void SelectOrdinarySurvivor(SurvivorDef survivor)
    {
        Check(survivor && IsOrdinarySurvivorAvailable(survivor) && OrdinarySurvivorChoices().Contains(survivor),
              "Unavailable survivor selection");
        r.selectedSurvivor = survivor.cachedName;
        Save();
        if (offlineStartVisible)
            ResetOfflineLoadoutSelection();
    }
    void DrawOfflineSurvivorRoster(SurvivorDef[] roster, SurvivorDef[] choices)
    {
        float width = Mathf.Min(Screen.width - 40, 1120), height = Mathf.Min(450, Screen.height * .48f),
              top = Mathf.Max(175, Screen.height * .25f);
        var panel = new Rect(20, top, width, height);
        GUI.Box(panel, "Survivors · original catalog / Android profile");
        const float gap = 8;
        float contentWidth = width - 42;
        int columns = Mathf.Max(1, Mathf.FloorToInt((contentWidth + gap) / 210));
        float cardWidth = (contentWidth - gap * (columns - 1)) / columns;
        var view = new Rect(panel.x + 12, panel.y + 27, panel.width - 24, panel.height - 38);
        int rows = (roster.Length + columns - 1) / columns;
        var content = new Rect(0, 0, contentWidth, rows * 65 + 4);
        offlineRosterScroll = GUI.BeginScrollView(view, offlineRosterScroll, content);
        var style = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleLeft, fontSize = 16, wordWrap = true };
        for (int i = 0; i < roster.Length; i++)
        {
            var survivor = roster[i];
            bool available = choices.Contains(survivor), selected = survivor.cachedName == r.selectedSurvivor;
            var rect = new Rect((i % columns) * (cardWidth + gap), (i / columns) * 65, cardWidth, 57);
            var name = RecoveredHudPresentation.Label(survivor.displayNameToken);
            if (string.IsNullOrEmpty(name) || name == survivor.displayNameToken)
                name = survivor.cachedName;
            string state = available                                                              ? "Available"
                           : survivor.GetRequiredExpansion() || survivor.GetRequiredEntitlement() ? "Expansion unavailable"
                                                                                                  : "Locked";
            var enabled = GUI.enabled;
            var tint = GUI.backgroundColor;
            GUI.enabled = available;
            GUI.backgroundColor = selected ? Color.Lerp(Color.white, survivor.primaryColor, .55f) : Color.white;
            if (GUI.Button(rect, (selected ? "▶ " : "") + name + "\n" + state, style))
                SelectOrdinarySurvivor(survivor);
            GUI.enabled = enabled;
            GUI.backgroundColor = tint;
        }
        GUI.EndScrollView();
    }
    void ConfirmSelectedSurvivorUnlock()
    {
        if (r.developerSurvivorOverride || string.IsNullOrEmpty(r.selectedSurvivor))
            return;
        var survivor =
            WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef, Array.Empty<SurvivorDef>())
                .SingleOrDefault(value => value && value.cachedName == r.selectedSurvivor);
        Check(survivor != null, "Selected survivor missing when native profile loaded");
        var name = SurvivorUnlockName(survivor);
        if (string.IsNullOrEmpty(name))
            return;
        var definition = UnlockableCatalog.GetUnlockableDef(name);
        Check(definition && definition.cachedName == name && (!survivor.unlockableDef || survivor.unlockableDef == definition) &&
                  HasOwnedProfileUnlock(definition),
              "Selected survivor lacks its original Android profile unlock");
    }
    bool SelectedSourceSurvivor()
    {
        return r != null && !string.IsNullOrEmpty(r.selectedSurvivor) && r.selectedSurvivor != "Commando";
    }
    GameObject SelectedPlayerPrefab(SessionConfig cfg)
    {
        if (string.IsNullOrEmpty(r.selectedSurvivor))
            r.selectedSurvivor = "Commando";
        if (r.selectedSurvivor == "Commando")
            return artifactBundle.LoadAsset<GameObject>(cfg.bodyAsset);
        Check(cfg.integratedWorld && r.liveCatalogs != null, "Unsupported offline survivor selection");
        var definitions =
            WholeCatalogComposed.CategoryFamily(RoR2.ContentManagement.AddressablesLabels.survivorDef, Array.Empty<SurvivorDef>());
        var survivor = definitions.SingleOrDefault(value => value && value.cachedName == r.selectedSurvivor);
        Check(survivor && survivor.bodyPrefab && !survivor.hidden && !survivor.GetRequiredExpansion() && !survivor.GetRequiredEntitlement(),
              "Selected survivor requires an unavailable original expansion or entitlement");
        bool locked = !string.IsNullOrEmpty(SurvivorUnlockName(survivor));
        Check(!locked || IsOrdinarySurvivorAvailable(survivor) ||
                  r.developerSurvivorOverride && r.debugOptions != null && !string.IsNullOrWhiteSpace(r.debugOptions.purpose) &&
                      r.debugOptions.purpose.Length <= 160,
              "Selected survivor requires an original unlock; developer selection needs an explicit diagnostic purpose");
        Check(!r.developerSurvivorOverride || locked, "Developer survivor override is limited to locked base survivors");
        var body = survivor.bodyPrefab.GetComponent<CharacterBody>();
        Check(body && body.bodyIndex != BodyIndex.None && BodyCatalog.GetBodyPrefab(body.bodyIndex) == survivor.bodyPrefab,
              "Selected source survivor/body catalog identity differs");
        return survivor.bodyPrefab;
    }
    void ObserveSourceAnimationEvents(CharacterBody player, float elapsed)
    {
        if (!SelectedSourceSurvivor() || r.sourceAnimationEvents != null && elapsed < nextSourceAnimationObservation)
            return;
        nextSourceAnimationObservation = elapsed + 2f;
        var model = player.modelLocator ? player.modelLocator.modelTransform : null;
        if (!model)
            return;
        var events = model.GetComponent<AnimationEvents>();
        var character = model.GetComponent<CharacterModel>();
        var locator = model.GetComponent<ChildLocator>();
        if (!events)
            return;
        var flags = BindingFlags.Instance | BindingFlags.NonPublic;
        var locatorField = typeof(AnimationEvents).GetField("childLocator", flags);
        var bodyField = typeof(AnimationEvents).GetField("bodyObject", flags);
        Check(locatorField != null && bodyField != null, "Original animation-event cache contract changed");
        var cachedLocator = locatorField.GetValue(events) as ChildLocator;
        var cachedBody = bodyField.GetValue(events) as GameObject;
        r.sourceAnimationEvents =
            new SourceAnimationEventReport { model = model.name,
                                             seconds = elapsed,
                                             componentEnabled = events.enabled,
                                             modelActive = model.gameObject.activeInHierarchy,
                                             characterBodyMatched = character && character.body == player,
                                             locatorPresent = locator,
                                             cachedLocator = cachedLocator == locator,
                                             cachedBody = cachedBody == player.gameObject,
                                             airstrikeMuzzles = r.selectedSurvivor == "Captain"
                                                                    ? new[] { "MuzzleAirstrike1", "MuzzleAirstrike2", "MuzzleAirstrike3" }
                                                                          .Select(name => locator && locator.FindChild(name))
                                                                          .ToArray()
                                                                    : null };
    }
}
