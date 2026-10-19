// Subsystem: progression (game path). Owner map: docs/ARCHITECTURE.md#ownership.
// Session phases: setup ResetOfflineLoadoutSelection, DrawOfflineLoadout; teardown —.
using System;
using System.Linq;
using RoR2;
using RoR2.Skills;
using UnityEngine;

// The menu edits only choices the original prefab exposes and the verified
// Android profile has earned. The native Loadout remains the serialization owner.
public sealed partial class PortSession
{
    Loadout offlinePendingLoadout;
    bool offlineLoadoutEdited, offlineLoadoutVisible;
    Vector2 offlineLoadoutScroll;
    void ResetOfflineLoadoutSelection()
    {
        offlinePendingLoadout =
            AndroidOfflineProfile.PreviewLoadout(System.IO.Path.Combine(Application.persistentDataPath, "android-profile-v1"));
        offlineLoadoutEdited = false;
        offlineLoadoutScroll = Vector2.zero;
    }

    GameObject OfflineLoadoutBody()
    {
        var survivor = (offlineMenuRoster ?? VisibleSurvivorRoster()).Single(value => value.cachedName == r.selectedSurvivor);
        Check(survivor.bodyPrefab &&
                  BodyCatalog.GetBodyPrefab(survivor.bodyPrefab.GetComponent<CharacterBody>().bodyIndex) == survivor.bodyPrefab,
              "Selected original loadout body identity differs");
        return survivor.bodyPrefab;
    }
    static string LoadoutLabel(string token, string fallback)
    {
        var label = RecoveredHudPresentation.Label(token);
        return string.IsNullOrEmpty(label) || label == token ? fallback : label;
    }
    bool OfflineSkinAvailable(SkinDef skin)
    {
        if (!skin || !string.IsNullOrEmpty(skin.unlockableName))
            return false;
        var def = skin.unlockableDef;
        return !def || !def.requiredExpansion && offlineUnlockPreview.Contains(def.cachedName);
    }
    bool OfflineSkillAvailable(SkillFamily.Variant variant)
    {
        if (!variant.skillDef || !string.IsNullOrEmpty(variant.unlockableName))
            return false;
        var def = variant.unlockableDef;
        return !def || !def.requiredExpansion && offlineUnlockPreview.Contains(def.cachedName);
    }
    static int[] OfflineLoadoutSlotIndices(GenericSkill[] slots)
    {
        // Keep the original component indices used by Loadout serialization.
        // Character-select visibility differs from loadout visibility (Captain).
        return Enumerable.Range(0, slots.Length).Where(index => slots[index] && !slots[index].hideInLoadoutSelect).ToArray();
    }
    void CycleOfflineSkin(int direction)
    {
        var prefab = OfflineLoadoutBody();
        var body = prefab.GetComponent<CharacterBody>().bodyIndex;
        var locator = prefab.GetComponent<ModelLocator>();
        var controller = locator && locator.modelTransform ? locator.modelTransform.GetComponent<ModelSkinController>() : null;
        Check(controller && controller.skins.Length > 0, "Original selected body has no skin controller");
        int current = (int)offlinePendingLoadout.bodyLoadoutManager.GetSkinIndex(body);
        Check(current >= 0 && current < controller.skins.Length && OfflineSkinAvailable(controller.skins[current]),
              "Saved original skin is unavailable at menu");
        for (int step = 1; step < controller.skins.Length; step++)
        {
            int next = (current + direction * step + controller.skins.Length * 2) % controller.skins.Length;
            if (!OfflineSkinAvailable(controller.skins[next]))
                continue;
            offlinePendingLoadout.bodyLoadoutManager.SetSkinIndex(body, (uint)next);
            offlineLoadoutEdited = true;
            return;
        }
    }
    void CycleOfflineSkill(int slot, int direction)
    {
        var prefab = OfflineLoadoutBody();
        var body = prefab.GetComponent<CharacterBody>().bodyIndex;
        var skills = prefab.GetComponents<GenericSkill>();
        Check(slot >= 0 && slot < skills.Length && skills[slot].skillFamily, "Original selected skill slot unavailable");
        var variants = skills[slot].skillFamily.variants;
        int current = (int)offlinePendingLoadout.bodyLoadoutManager.GetSkillVariant(body, slot);
        Check(current >= 0 && current < variants.Length && OfflineSkillAvailable(variants[current]),
              "Saved original skill variant is unavailable at menu");
        for (int step = 1; step < variants.Length; step++)
        {
            int next = (current + direction * step + variants.Length * 2) % variants.Length;
            if (!OfflineSkillAvailable(variants[next]))
                continue;
            offlinePendingLoadout.bodyLoadoutManager.SetSkillVariant(body, slot, (uint)next);
            offlineLoadoutEdited = true;
            return;
        }
    }
    void DrawOfflineLoadout()
    {
        Check(offlinePendingLoadout != null && offlineUnlockPreview != null, "Original loadout menu lacks a verified profile preview");
        var prefab = OfflineLoadoutBody();
        var body = prefab.GetComponent<CharacterBody>().bodyIndex;
        var locator = prefab.GetComponent<ModelLocator>();
        var controller = locator && locator.modelTransform ? locator.modelTransform.GetComponent<ModelSkinController>() : null;
        Check(controller && controller.skins.Length > 0, "Original selected body skin list unavailable");
        var slots = prefab.GetComponents<GenericSkill>();
        var visibleSlots = OfflineLoadoutSlotIndices(slots);
        float width = Mathf.Min(Screen.width - 40, 760), top = Mathf.Max(60, Screen.height * .18f);
        float height = Mathf.Min(480, Screen.height - top - 180);
        GUI.Box(new Rect(20, top, width, height), "Loadout");
        var view = new Rect(32, top + 32, width - 24, height - 94);
        float rowWidth = view.width - 20;
        var skinIndex = (int)offlinePendingLoadout.bodyLoadoutManager.GetSkinIndex(body);
        Check(skinIndex >= 0 && skinIndex < controller.skins.Length && OfflineSkinAvailable(controller.skins[skinIndex]),
              "Original profile skin selection unavailable");
        var skin = controller.skins[skinIndex];
        offlineLoadoutScroll =
            GUI.BeginScrollView(view, offlineLoadoutScroll, new Rect(0, 0, rowWidth, (visibleSlots.Length + 1) * 58 + 8));
        try
        {
            GUI.Label(new Rect(12, 6, rowWidth - 112, 42), "Skin: " + LoadoutLabel(skin.nameToken, skin.name));
            if (GUI.Button(new Rect(rowWidth - 87, 6, 75, 38), "◀  ▶"))
                CycleOfflineSkin(1);
            for (int row = 0; row < visibleSlots.Length; row++)
            {
                int i = visibleSlots[row];
                var family = slots[i].skillFamily;
                Check(family && family.variants.Length > 0, "Original selected body skill family unavailable");
                int index = (int)offlinePendingLoadout.bodyLoadoutManager.GetSkillVariant(body, i);
                Check(index >= 0 && index < family.variants.Length && OfflineSkillAvailable(family.variants[index]),
                      "Original profile skill selection unavailable");
                var skill = family.variants[index].skillDef;
                float y = 6 + (row + 1) * 58;
                var title = LoadoutLabel(slots[i].loadoutTitleToken, slots[i].skillName);
                GUI.Label(new Rect(12, y, rowWidth - 112, 42), title + ": " + LoadoutLabel(skill.skillNameToken, skill.skillName));
                if (GUI.Button(new Rect(rowWidth - 87, y, 75, 38), "◀  ▶"))
                    CycleOfflineSkill(i, 1);
            }
        }
        finally
        {
            GUI.EndScrollView();
        }
        GUI.Label(new Rect(44, top + height - 54, width - 64, 48),
                  "Changes save when you start a run. Switching survivor discards pending changes.",
                  new GUIStyle(GUI.skin.label) { wordWrap = true });
    }
}
