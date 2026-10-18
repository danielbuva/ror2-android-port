using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Xml.Linq;
using RoR2;
using RoR2.Stats;
using UnityEditor;
using UnityEngine;

// Cheap native-serializer/storage checks in an owned host fixture, never Play Mode.
// Full catalog sizes, session lifecycle and ARM64 still require the composed game.
public static class AndroidProfileHost
{
    [Serializable]
    sealed class LegacyGeneration
    {
        public int version = 1;
        public string xml, sha256;
        public string[] appliedRuns;
    }
    static void WriteLegacy(string path, string xml, params Guid[] applied)
    {
        var value = new LegacyGeneration { xml = xml, appliedRuns = applied.Select(id => id.ToString("N")).ToArray() };
        using (var hash = SHA256.Create()) value.sha256 =
            BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(xml + "\n" + string.Join("\n", value.appliedRuns))))
                .Replace("-", "")
                .ToLowerInvariant();
        File.WriteAllText(path, JsonUtility.ToJson(value));
    }
    public static object Run(string directory)
    {
        if (EditorApplication.isPlaying || EditorApplication.isCompiling ||
            !System.IO.Path.GetFullPath(directory).Contains("/work/experiments/whole-catalog/gameplay/profile-") ||
            Directory.Exists(directory))
            throw new Exception("Require new ignored host profile fixture and idle editor");
        var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
        var fields =
            new[] { typeof(StatSheet).GetField("fieldsTemplate", flags), typeof(StatSheet).GetField("nonDefaultFieldsBuffer", flags),
                    typeof(SurvivorCatalog).GetField("survivorDefs", flags), typeof(SurvivorCatalog).GetField("cachedSurvivorNames", flags),
                    typeof(XmlUtility).GetField("ValueReplacements", flags) };
        var before = fields.Select(field => field.GetValue(null)).ToArray();
        var oldDefault = UserProfile.defaultProfile;
        var oldSurvivor = SurvivorCatalog.defaultSurvivor;
        try
        {
            var survivor = AssetDatabase.LoadAssetAtPath<SurvivorDef>("Assets/WholeGame/RoR2/Base/Characters/Commando/Commando.asset");
            var redirects =
                AssetDatabase.LoadAssetAtPath<UserProfileRedirectData>("Assets/WholeGame/RoR2/Base/Core/UserProfileRedirects.asset");
            if (!survivor || !redirects)
                throw new Exception("Source profile fixture assets absent");
            var stats = StatDef.allStatDefs.Select(def => new StatField { statDef = def }).ToArray();
            fields[0].SetValue(null, stats);
            fields[1].SetValue(null, new bool[stats.Length]);
            fields[2].SetValue(null, new[] { survivor });
            fields[3].SetValue(null, new[] { survivor.cachedName });
            fields[4].SetValue(null, redirects);
            SurvivorCatalog.defaultSurvivor = survivor;
            if (UserProfile.saveFields == null)
                UserProfile.GenerateSaveFieldFunctions();
            UserProfile.LoadDefaultProfile();
            var baseline = Guid.NewGuid();
            var store = new AndroidOfflineProfile(directory, new[] { baseline });
            if (store.profile.loggedIn || store.profile.saveID != 0 || store.profile.coins != 0 || store.profile.keyboardMap != null ||
                store.profile.mouseMap != null || store.profile.joystickMap != null)
                throw new Exception("Fresh profile claims platform/controller capability");
            store.profile.name = "Native host fixture";
            var delta = StatSheet.New();
            delta.PushStatValue(StatDef.totalKills, 3UL);
            var run = Guid.NewGuid();
            if (store.ShouldApply(baseline) || store.ApplyResult(baseline, delta) || store.appliedRuns != 0 ||
                store.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 0)
                throw new Exception("Historical baseline imported statistics");
            if (!store.ApplyResult(run, delta) || store.ApplyResult(run, delta))
                throw new Exception("Result deduplication failed");
            store.Save();
            var nextRun = Guid.NewGuid();
            var loaded = new AndroidOfflineProfile(directory, new[] { baseline, run, nextRun });
            if (loaded.recovery != "validated-primary" || loaded.profile.name != store.profile.name ||
                loaded.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 3 || loaded.appliedRuns != 1 ||
                loaded.baselineRuns != 1 || loaded.ShouldApply(baseline) || loaded.ShouldApply(run) || !loaded.ShouldApply(nextRun))
                throw new Exception("Cold native profile/baseline differs");
            var path = System.IO.Path.Combine(directory, "profile.json");
            File.WriteAllText(path + ".pending", "interrupted owned fixture");
            var interrupted = new AndroidOfflineProfile(directory);
            if (interrupted.recovery != "validated-primary" || interrupted.appliedRuns != 1)
                throw new Exception("Pending write replaced primary");
            File.WriteAllText(path, "corrupt owned fixture");
            var restored = new AndroidOfflineProfile(directory);
            if (restored.recovery != "validated-backup" || restored.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 3 ||
                restored.appliedRuns != 1 || Directory.GetFiles(directory, "*.rejected-*").Length != 1)
                throw new Exception("Backup restoration differs");
            // A lost newest generation remains eligible for replay; the baseline does not.
            if (!restored.ApplyResult(nextRun, delta))
                throw new Exception("New result did not apply");
            File.WriteAllText(path, "interrupted latest primary");
            var replay = new AndroidOfflineProfile(directory, new[] { nextRun });
            if (!replay.ShouldApply(nextRun) || replay.ShouldApply(baseline) ||
                replay.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 3 || !replay.ApplyResult(nextRun, delta) ||
                replay.ApplyResult(nextRun, delta) || replay.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 6)
                throw new Exception("Recovered result reconciliation eligibility differs");
            File.Copy(path, path + ".pending", true);
            File.WriteAllText(path, "bad primary before pending recovery");
            File.WriteAllText(path + ".backup", "bad backup before pending recovery");
            int rejected = Directory.GetFiles(directory, "*.rejected-*").Length;
            var pending = new AndroidOfflineProfile(directory);
            if (pending.recovery != "validated-pending" || pending.appliedRuns != 2 || pending.ShouldApply(baseline) ||
                pending.ShouldApply(nextRun) || pending.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 6 ||
                Directory.GetFiles(directory, "*.rejected-*").Length != rejected + 2)
                throw new Exception("Valid pending recovery/rejected evidence differs");
            var migration = System.IO.Path.Combine(directory, "migration");
            Directory.CreateDirectory(migration);
            var legacyPath = System.IO.Path.Combine(migration, "profile.json");
            string xml = UserProfile.ToXml(store.profile).ToString(SaveOptions.DisableFormatting);
            WriteLegacy(legacyPath, xml, run);
            WriteLegacy(legacyPath + ".backup", xml, run);
            string beforeMigration = File.ReadAllText(legacyPath);
            bool missingBaselineRejected = false;
            try
            {
                new AndroidOfflineProfile(migration);
            }
            catch (InvalidOperationException)
            {
                missingBaselineRejected = true;
            }
            if (!missingBaselineRejected || File.ReadAllText(legacyPath) != beforeMigration)
                throw new Exception("Legacy migration accepted an unknown baseline");
            var migrated = new AndroidOfflineProfile(migration, new[] { baseline, run });
            if (migrated.recovery != "validated-primary-migrated-v1" || migrated.baselineRuns != 1 || migrated.appliedRuns != 1 ||
                migrated.ShouldApply(run) || migrated.ShouldApply(baseline) || !migrated.ShouldApply(nextRun) ||
                UserProfile.ToXml(migrated.profile).ToString(SaveOptions.DisableFormatting) != xml)
                throw new Exception("Legacy migration changed original data/eligibility");
            File.WriteAllText(legacyPath, "migration primary interrupted");
            var migratedBackup = new AndroidOfflineProfile(migration, new[] { nextRun });
            if (migratedBackup.recovery != "validated-backup" || migratedBackup.ShouldApply(baseline) ||
                !migratedBackup.ShouldApply(nextRun) || migratedBackup.appliedRuns != 1)
                throw new Exception("Migrated fallback did not retain original baseline");
            // A v2 primary with a v1 fallback models interruption between migration writes.
            WriteLegacy(legacyPath + ".backup", xml, run);
            var resumedMigration = new AndroidOfflineProfile(migration, new[] { nextRun });
            File.WriteAllText(legacyPath, "resumed migration primary interrupted");
            var resumedBackup = new AndroidOfflineProfile(migration);
            if (resumedBackup.recovery != "validated-backup" || resumedBackup.ShouldApply(baseline) ||
                !resumedBackup.ShouldApply(nextRun) || resumedBackup.appliedRuns != 1)
                throw new Exception("Interrupted migration fallback differs");
            var hardware = System.IO.Path.Combine(directory, "hardware-rejected");
            Directory.CreateDirectory(hardware);
            var mapXml = XDocument.Parse(xml);
            mapXml.Root.Element("HardwareJoystickMaps2").Value = "{\"Entries\":[{\"HWGuid\":\"not-a-guid\",\"XMLMap\":\"unavailable\"}]}";
            WriteLegacy(System.IO.Path.Combine(hardware, "profile.json"), mapXml.ToString(SaveOptions.DisableFormatting), run);
            bool hardwareRejected = false;
            try
            {
                new AndroidOfflineProfile(hardware);
            }
            catch (InvalidDataException)
            {
                hardwareRejected = true;
            }
            if (!hardwareRejected)
                throw new Exception("Hardware map reached native profile parsing");
            foreach (bool duplicate in new[] { false, true })
            {
                var incompatible = System.IO.Path.Combine(directory, duplicate ? "duplicate-unlock" : "unknown-unlock");
                Directory.CreateDirectory(incompatible);
                var incompatiblePath = System.IO.Path.Combine(incompatible, "profile.json");
                var unlockXml = XDocument.Parse(xml);
                unlockXml.Root.Element("stats").Add(new XElement("unlock", "Android.Host.UnknownUnlock"));
                if (duplicate)
                    unlockXml.Root.Element("stats").Add(new XElement("unlock", "Android.Host.UnknownUnlock"));
                WriteLegacy(incompatiblePath, unlockXml.ToString(SaveOptions.DisableFormatting), run);
                WriteLegacy(incompatiblePath + ".backup", xml, run);
                string incompatibleBytes = File.ReadAllText(incompatiblePath), backupBytes = File.ReadAllText(incompatiblePath + ".backup");
                bool incompatibleRejected = false;
                try
                {
                    new AndroidOfflineProfile(incompatible, new[] { baseline });
                }
                catch (InvalidOperationException)
                {
                    incompatibleRejected = true;
                }
                if (!incompatibleRejected || File.ReadAllText(incompatiblePath) != incompatibleBytes ||
                    File.ReadAllText(incompatiblePath + ".backup") != backupBytes || Directory.GetFiles(incompatible).Length != 2)
                    throw new Exception("Unlock incompatibility lost data or fell back to an older generation");
            }
            // Callback mutations model an earned reward; these synthetic values never
            // leave this ignored host fixture or enter a player profile.
            var transactionPath = System.IO.Path.Combine(directory, "transaction");
            int callbacks = 0;
            bool failCallback = true;
            Action<UserProfile> progression = candidate =>
            {
                callbacks++;
                if (candidate.canSave || candidate.statSheet.GetStatValueULong(StatDef.totalKills) != 3)
                    throw new Exception("Progression did not receive a detached post-delta profile");
                candidate.name = "Transaction host fixture";
                candidate.coins += 7;
                candidate.totalCollectedCoins += 7;
                if (failCallback)
                    throw new InvalidOperationException("Injected progression failure");
            };
            var transaction = new AndroidOfflineProfile(transactionPath, new[] { baseline }, progression);
            var originalProfile = transaction.profile;
            var transactionFile = System.IO.Path.Combine(transactionPath, "profile.json");
            string originalBytes = File.ReadAllText(transactionFile), originalBackup = File.ReadAllText(transactionFile + ".backup");
            var transactionRun = Guid.NewGuid();
            if (callbacks != 0 || transaction.ApplyResult(baseline, delta) || callbacks != 0)
                throw new Exception("Load/baseline dispatched progression");
            bool failedAtomically = false;
            try
            {
                transaction.ApplyResult(transactionRun, delta);
            }
            catch (InvalidOperationException error)
            {
                failedAtomically = error.Message == "Injected progression failure";
            }
            if (!failedAtomically || callbacks != 1 || !ReferenceEquals(transaction.profile, originalProfile) ||
                transaction.profile.coins != 0 || transaction.profile.totalCollectedCoins != 0 ||
                transaction.profile.statSheet.GetStatValueULong(StatDef.totalKills) != 0 || transaction.appliedRuns != 0 ||
                !transaction.ShouldApply(transactionRun) || File.ReadAllText(transactionFile) != originalBytes ||
                File.ReadAllText(transactionFile + ".backup") != originalBackup || Directory.GetFiles(transactionPath).Length != 2)
                throw new Exception("Failed progression escaped its transaction");
            failCallback = false;
            if (!transaction.ApplyResult(transactionRun, delta) || transaction.ApplyResult(transactionRun, delta) || callbacks != 2 ||
                transaction.profile.coins != 7 || transaction.profile.totalCollectedCoins != 7 || transaction.appliedRuns != 1)
                throw new Exception("Progression retry/deduplication differs");
            string awardedBytes = File.ReadAllText(transactionFile);
            var transactionReload = new AndroidOfflineProfile(transactionPath, new[] { baseline }, progression);
            if (callbacks != 2 || transactionReload.profile.name != "Transaction host fixture" || transactionReload.profile.coins != 7 ||
                transactionReload.profile.totalCollectedCoins != 7 || transactionReload.ApplyResult(transactionRun, delta) ||
                callbacks != 2)
                throw new Exception("Cold reload re-awarded progression");
            File.WriteAllText(transactionFile, "interrupted reward generation");
            var transactionReplay = new AndroidOfflineProfile(transactionPath, new[] { baseline }, progression);
            if (transactionReplay.recovery != "validated-backup" || callbacks != 2 || !transactionReplay.ShouldApply(transactionRun) ||
                !transactionReplay.ApplyResult(transactionRun, delta) || transactionReplay.ApplyResult(transactionRun, delta) ||
                callbacks != 3 || File.ReadAllText(transactionFile) != awardedBytes)
                throw new Exception("Recovered progression did not replay exactly once");
            return new { success = true,
                         saveFields = UserProfile.saveFields.Length,
                         fixtureStatFields = stats.Length,
                         nativeXml = true,
                         resultDeduplicated = true,
                         baselineSkipped = true,
                         baselineImmutable = true,
                         coldReload = true,
                         interruptedPendingIgnored = true,
                         backupRecovered = true,
                         resultReplayEligible = true,
                         pendingRecoveredAfterCorruptBackup = true,
                         rejectedEvidenceRetained = true,
                         legacyMigrationPreservesNativeData = true,
                         migrationFallbackHasBaseline = true,
                         interruptedMigrationRecovered = true,
                         hardwareMapsRejected = true,
                         unknownAndDuplicateUnlocksPreserved = true,
                         progressionAtomicFailure = true,
                         progressionRetryDeduplicated = true,
                         progressionColdReload = true,
                         progressionRecoveredExactly = true,
                         platformLogin = false,
                         controllerMapsAvailable = false };
        }
        finally
        {
            for (int i = 0; i < fields.Length; i++)
                fields[i].SetValue(null, before[i]);
            UserProfile.defaultProfile = oldDefault;
            SurvivorCatalog.defaultSurvivor = oldSurvivor;
        }
    }
}
