#if UNITY_EDITOR
using System;
using System.Reflection;
using RoR2;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Verifies the accepted native property setter's effect on an inactive component.
// No content, Run, server, NetworkUser or lifecycle callback is fabricated.
public static class NativeDirectorDeckSetterFixture
{
    const BindingFlags PrivateInstance = BindingFlags.Instance | BindingFlags.NonPublic;

    static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("Native director deck-setter fixture failed: " + message);
    }

    static object PrivateField(CombatDirector director, string name)
    {
        var field = typeof(CombatDirector).GetField(name, PrivateInstance);
        Require(field != null, "Missing native initialization field: " + name);
        return field.GetValue(director);
    }

    public static object Run()
    {
        Require(!EditorApplication.isPlaying && !EditorApplication.isCompiling && !NetworkServer.active && !NetworkClient.active &&
                    !RoR2.Run.instance,
                "Requires an idle editor without a Run or network session");
        GameObject host = null;
        DirectorCardCategorySelection deck = null;
        try
        {
            host = new GameObject("Owned native deck-setter fixture");
            host.SetActive(false);
            var director = host.AddComponent<CombatDirector>();
            deck = ScriptableObject.CreateInstance<DirectorCardCategorySelection>();
            deck.categories = Array.Empty<DirectorCardCategorySelection.Category>();
            Require(director && !host.activeInHierarchy && !CombatDirector.instancesList.Contains(director) &&
                        PrivateField(director, "rng") == null && PrivateField(director, "moneyWaves") == null &&
                        PrivateField(director, "monsterCardsSelection") == null,
                    "Fresh inactive component did not have the accepted cold field state");
            director.monsterCards = deck;
            var selection = PrivateField(director, "monsterCardsSelection") as WeightedSelection<DirectorCard>;
            Require(ReferenceEquals(director.monsterCards, deck) && selection != null && selection.Count == 0 &&
                        PrivateField(director, "rng") == null && PrivateField(director, "moneyWaves") == null && !host.activeInHierarchy &&
                        !CombatDirector.instancesList.Contains(director),
                    "Native deck binding did not build only its card selection while the component remained cold");
            director.monsterCards = deck;
            Require(ReferenceEquals(PrivateField(director, "monsterCardsSelection"), selection),
                    "Repeated exact deck assignment unexpectedly rebuilt selection");
            director.monsterCards = null;
            Require(PrivateField(director, "monsterCardsSelection") == null && PrivateField(director, "rng") == null &&
                        PrivateField(director, "moneyWaves") == null && !host.activeInHierarchy &&
                        !CombatDirector.instancesList.Contains(director),
                    "Native null-deck restoration changed the cold lifecycle state");
            return new { nativeSetterBuildsSelectionBeforeAwake = true, rngAndMoneyWavesRemainCold = true,
                         exactDeckAssignmentIdempotent = true, nativeNullDeckRestored = true,
                         sceneActivationOrStageExecutionClaimed = false };
        }
        finally
        {
            if (host)
                UnityEngine.Object.DestroyImmediate(host);
            if (deck)
                UnityEngine.Object.DestroyImmediate(deck);
        }
    }
}
#endif
