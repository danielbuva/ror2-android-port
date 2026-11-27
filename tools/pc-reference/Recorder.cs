using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx;
using EntityStates;
using Facepunch.Steamworks;
using HarmonyLib;
using RoR2;
using RoR2.CharacterAI;
using RoR2.ExpansionManagement;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Zio.FileSystems;
using GameConsole = RoR2.Console;
using Path = System.IO.Path;

namespace Ror2Lab.Reference
{
    [BepInPlugin(PluginId, "RoR2 Lab PC Reference", "1.0.0")]
    public sealed class Recorder : BaseUnityPlugin
    {
        private const string PluginId = "dev.ror2lab.pc-reference";
        private const string RequestSwitch = "--ror2lab-reference";
        private static Recorder active;
        private readonly Dictionary<string, CharacterMaster> actors = new Dictionary<string, CharacterMaster>();
        private readonly List<AudioEvent> audio = new List<AudioEvent>();
        private readonly List<StepResult> steps = new List<StepResult>();
        private readonly RecordingCamera camera = new RecordingCamera();
        private CaptureRequest request;
        private MemoryFileSystem profileStorage;
        private string output;
        private string stepId;
        private string waveStatus = "not_requested";
        private bool waveRecording;
        private UserProfile profile;
        private Harmony harmony;
        private bool finished;
        private CharacterBody aimSubject;
        private Vector3 aimPoint;

        private void Awake()
        {
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, RequestSwitch);
            if (index < 0 || index + 1 >= args.Length)
            {
                Logger.LogError("The reference copy must be started through ./dev pc-reference.");
                Application.Quit(1);
                return;
            }
            try
            {
                string file = args[index + 1];
                output = Path.GetDirectoryName(file);
                request = JsonUtility.FromJson<CaptureRequest>(File.ReadAllText(file));
                // The game's callback fires only after its own Steam DLL and subscription checks.
                SteamworksClientManager.onLoaded += IsolateProfile;
                StartCoroutine(Drive());
            }
            catch (Exception error)
            {
                Finish(error);
            }
        }

        private void IsolateProfile()
        {
            if (RoR2Application.loadFinished)
            {
                Finish(new InvalidOperationException("Profile isolation missed the Steam initialization callback."));
                return;
            }
            profileStorage = new MemoryFileSystem();
            RoR2Application.cloudStorage = profileStorage;
            PlatformSystems.achievementSystem = new ReferenceAchievements();
            if (Client.Instance == null || !Client.Instance.IsLoggedOn)
                Finish(new InvalidOperationException("NEED owner: stock Steam initialization requires a signed-in owner."));
        }

        private IEnumerator Drive()
        {
            // Unity doesn't propagate exceptions from a nested coroutine to its parent.
            var pending = new Stack<IEnumerator>();
            pending.Push(Record());
            while (pending.Count != 0 && !finished)
            {
                IEnumerator routine = pending.Peek();
                object wait = null;
                try
                {
                    if (!routine.MoveNext())
                    {
                        pending.Pop();
                        continue;
                    }
                    wait = routine.Current;
                }
                catch (Exception error)
                {
                    Finish(error);
                    yield break;
                }
                if (wait is IEnumerator nested)
                    pending.Push(nested);
                else
                    yield return wait;
            }
            Finish(null);
        }

        private static IEnumerator Until(Func<bool> condition, string description, float timeout = 60)
        {
            float deadline = Time.realtimeSinceStartup + timeout;
            while (!condition())
            {
                if (Time.realtimeSinceStartup >= deadline)
                    throw new TimeoutException(description);
                yield return null;
            }
        }

        private IEnumerator Record()
        {
            yield return Until(() => profileStorage != null, "Stock Steam initialization never authorized a signed-in owner.", 90);
            yield return Until(() => RoR2Application.loadFinished && RoR2Application.IsMainMenuInitialized &&
                RoR2Application.IsEntitlementsUpdated, "Title or entitlement catalog never became ready.", 90);
            if (RoR2Application.cloudStorage != profileStorage || LocalUserManager.isAnyUserSignedIn)
                throw new InvalidOperationException("Failed to establish an isolated local profile.");
            if (SystemInfo.graphicsDeviceType != GraphicsDeviceType.Direct3D11)
                throw new InvalidOperationException("The reference plan requires the D3D11 renderer.");
            profile = PlatformSystems.saveSystem.CreateProfile(profileStorage, "Lab Reference");
            LocalUserManager.SetLocalUsers(new[] { new LocalUserManager.LocalUserInitializationInfo { profile = profile } });
            var local = LocalUserManager.GetFirstLocalUser();
            if (local == null || local.userProfile != profile)
                throw new InvalidOperationException("Fresh local user was not selected.");

            CaptureScenario scenario = request.scenario;
            BodyIndex bodyIndex = BodyCatalog.FindBodyIndex(scenario.body);
            SurvivorDef survivor = SurvivorCatalog.FindSurvivorDefFromBody(BodyCatalog.GetBodyPrefab(bodyIndex));
            if (bodyIndex == BodyIndex.None || !survivor)
                throw new ArgumentException("Unknown survivor body: " + scenario.body);
            ConfigureDisplay();
            ulong seed = ulong.Parse(scenario.seed, CultureInfo.InvariantCulture);
            PreGameController.overrideRunSeed.SetString(scenario.seed);
            GameConsole.instance.FindConVar("run_scene_override").SetString(scenario.naturalFirstStage ? "" : scenario.scene);
            GameConsole.instance.SubmitCmd(null, "transition_command \"gamemode ClassicRun; host 0;\"");
            yield return Until(() => PreGameController.instance && local.currentNetworkUser,
                "Native local lobby never created its user.");
            if (!NetworkServer.active || !NetworkServer.dontListen)
                throw new InvalidOperationException("Recorder requires a local server with incoming connections disabled.");
            NetworkUser user = local.currentNetworkUser;
            user.SetSurvivorPreferenceClient(survivor);
            yield return Until(() => user.bodyIndexPreference == bodyIndex &&
                PreGameRuleVoteController.FindForUser(user), "Lobby did not accept survivor selection.");
            RuleChoiceDef drizzle = RuleCatalog.FindChoiceDef("Difficulty.Easy");
            if (drizzle == null)
                throw new InvalidOperationException("Drizzle rule is missing.");
            PreGameRuleVoteController.FindForUser(user).SetVote(drizzle.ruleDef.globalIndex, drizzle.localIndex);
            yield return Until(() => PreGameController.instance.readOnlyRuleBook.FindDifficulty() == DifficultyIndex.Easy,
                "Lobby did not accept Drizzle.");
            PreGameController.instance.runSeed = seed;
            GameConsole.instance.SubmitCmd(null, "pregame_start_run");
            yield return Until(() => Run.instance && Stage.instance && user.GetCurrentBody(), "Stage never produced a player body.", 90);
            yield return Until(() => SceneManager.GetActiveScene().name == scenario.scene &&
                user.GetCurrentBody() && !user.GetCurrentBody().healthComponent.isInFrozenState, "Expected stage did not become active.");
            yield return Until(() => CameraRigController.readOnlyInstancesList.Any(rig => rig.viewer == user), "Player camera did not activate.");
            if (Run.instance.seed != seed || user.GetCurrentBody().bodyIndex != bodyIndex)
                throw new InvalidOperationException("Native run seed or survivor differs from the plan.");
            if (Screen.width != request.settings.width || Screen.height != request.settings.height)
                throw new InvalidOperationException($"Expected {request.settings.width}×{request.settings.height}, got {Screen.width}×{Screen.height}.");
            if (user.GetCurrentBody().currentVehicle)
                user.GetCurrentBody().currentVehicle.EjectPassenger();

            InstallAudioObserver();
            if (scenario.steps.Any(step => step.action == "grapple"))
                GrappleObservation.Install(harmony);
            if (scenario.captureAudio)
            {
                waveStatus = AkSoundEngine.StartOutputCapture(Path.Combine(output, "mix.wav")).ToString();
                waveRecording = waveStatus == AKRESULT.AK_Success.ToString();
            }
            camera.fov = request.settings.fov;
            CameraRigController rigController = CameraRigController.readOnlyInstancesList.First(rig => rig.viewer == user);
            foreach (CaptureStep step in scenario.steps)
                yield return RecordStep(step, user, rigController);
        }

        private void ConfigureDisplay()
        {
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = request.settings.fps;
            Application.runInBackground = true;
            if (!request.settings.disablePostProcessing)
                return;
            QualitySettings.shadows = ShadowQuality.Disable;
            foreach (string option in new[] { "pp_bloom", "pp_ao", "pp_screendistortion", "enable_screen_distortion" })
            {
                var conVar = GameConsole.instance.FindConVar(option);
                if (conVar == null)
                    throw new InvalidOperationException("Missing display setting: " + option);
                conVar.SetString("0");
            }
        }

        private IEnumerator RecordStep(CaptureStep step, NetworkUser user, CameraRigController rig)
        {
            stepId = step.id;
            if (waveRecording)
                AkSoundEngine.AddOutputCaptureMarker(stepId);
            CharacterBody player = user.GetCurrentBody();
            if (!player || !player.healthComponent.alive)
                throw new InvalidOperationException("Player died before " + stepId);
            if (step.player != null && step.player.Length != 0)
                TeleportHelper.TeleportBody(player, CaptureStep.Vector(step.player), true);
            if (step.view != null && step.view.position != null && step.view.position.Length != 0)
            {
                camera.state = new CameraState
                {
                    position = CaptureStep.Vector(step.view.position) + (step.view.relativeToPlayer ? player.footPosition : Vector3.zero),
                    rotation = Quaternion.Euler(step.view.pitch, step.view.yaw, 0),
                    fov = camera.fov
                };
                rig.SetOverrideCam(camera, 0);
            }

            CharacterBody subject = player;
            if (step.action == "spawn")
            {
                GameObject prefab = MasterCatalog.FindMasterPrefab(step.value);
                if (!prefab)
                    throw new ArgumentException("Unknown master prefab: " + step.value);
                CharacterMaster master = new MasterSummon
                {
                    masterPrefab = prefab,
                    position = CaptureStep.Vector(step.position) + (step.relativeToPlayer ? player.footPosition : Vector3.zero),
                    rotation = player.transform.rotation,
                    teamIndexOverride = TeamIndex.Monster
                }.Perform();
                if (!master)
                    throw new InvalidOperationException("Could not spawn " + step.value);
                actors.Add(step.subject, master);
                yield return Until(() => master && master.GetBody(), "Spawned master never produced a body.", 15);
                subject = master.GetBody();
                if (step.freezeAi)
                    foreach (BaseAI ai in master.GetComponents<BaseAI>())
                        ai.enabled = false;
            }
            else if (!string.IsNullOrEmpty(step.subject) && step.subject != "player")
            {
                subject = actors[step.subject].GetBody();
                if (!subject)
                    throw new InvalidOperationException("Capture actor has no live body: " + step.subject);
            }

            if (!string.IsNullOrEmpty(step.aimAt) || (step.aim != null && step.aim.Length != 0))
            {
                aimSubject = subject;
                aimPoint = string.IsNullOrEmpty(step.aimAt) ? CaptureStep.Vector(step.aim) :
                    step.aimAt == "player" ? player.corePosition : actors[step.aimAt].GetBody().corePosition;
                ApplyAim();
                yield return new WaitForSecondsRealtime(0.25f);
            }
            GrappleObservation grapple = null;
            switch (step.action)
            {
                case "state":
                    Type type = typeof(EntityState).Assembly.GetType(step.value, throwOnError: true);
                    if (type.IsAbstract || !typeof(EntityState).IsAssignableFrom(type))
                        throw new ArgumentException("Invalid entity state: " + step.value);
                    EntityStateMachine machine = EntityStateMachine.FindByCustomName(subject.gameObject, step.machine);
                    if (!machine)
                        throw new ArgumentException("Actor does not own state machine: " + step.machine);
                    machine.SetState((EntityState)Activator.CreateInstance(type));
                    break;
                case "skill":
                    GenericSkill skill = SelectSkill(subject.skillLocator, step.value);
                    if (!skill || !skill.ExecuteIfReady())
                        throw new InvalidOperationException($"Native skill {step.value} could not execute on {subject.name}.");
                    break;
                case "grapple":
                    if (subject != player || !(step.holdSeconds > 0 && step.recordSeconds > step.holdSeconds))
                        throw new ArgumentException("Grapple requires the local player and a recording window longer than the hold.");
                    grapple = GrappleObservation.Begin(player, step.holdSeconds);
                    StartCoroutine(grapple.SampleTicks());
                    break;
                case "ping":
                    user.master.GetComponent<PingerController>().DebugPingObject(subject);
                    break;
                case "fire-trail":
                    subject.AddBuff(RoR2Content.Buffs.AffixRed);
                    break;
                case "move":
                    Vector3 destination = CaptureStep.Vector(step.position) + (step.relativeToPlayer ? subject.footPosition : Vector3.zero);
                    yield return MoveActor(subject, destination, step.settleSeconds);
                    break;
                case "spawn":
                case "capture":
                    break;
                default:
                    throw new ArgumentException("Unrecognized action: " + step.action);
            }
            string folder = Path.Combine(output, stepId);
            Directory.CreateDirectory(folder);
            if (step.settleSeconds > 0 && step.action != "move")
                yield return new WaitForSecondsRealtime(step.settleSeconds);
            yield return new WaitForEndOfFrame();
            string image = Path.Combine(folder, "frame.png");
            WriteFrame(image);
            CaptureEvidence.WriteState(folder, rig.sceneCam, player, subject, step, scenario: request.scenario);
            var frameTimes = new List<FrameTime> { new FrameTime { frame = "frame.png", seconds = Time.realtimeSinceStartup } };
            float end = Time.realtimeSinceStartup + step.recordSeconds;
            while (Time.realtimeSinceStartup + 0.1f < end)
            {
                yield return new WaitForSecondsRealtime(0.1f);
                yield return new WaitForEndOfFrame();
                string name = $"frame-{frameTimes.Count:D4}.png";
                frameTimes.Add(new FrameTime { frame = name, seconds = Time.realtimeSinceStartup });
                WriteFrame(Path.Combine(folder, name));
            }
            grapple?.Write(folder);
            steps.Add(new StepResult { id = stepId, frame = stepId + "/frame.png", state = stepId + "/state.json",
                grapple_ticks = grapple == null ? null : stepId + "/grapple-ticks.jsonl", timeline = frameTimes.ToArray() });
        }

        private void LateUpdate() => ApplyAim();

        private void ApplyAim()
        {
            if (!aimSubject || !aimSubject.inputBank)
                return;
            Vector3 direction = (aimPoint - aimSubject.inputBank.aimOrigin).normalized;
            aimSubject.inputBank.aimDirection = direction;
            if (aimSubject.characterDirection)
                aimSubject.characterDirection.moveVector = Vector3.ProjectOnPlane(direction, Vector3.up).normalized;
        }

        private static GenericSkill SelectSkill(SkillLocator skills, string slot)
        {
            switch (slot)
            {
                case "primary": return skills.primary;
                case "secondary": return skills.secondary;
                case "utility": return skills.utility;
                case "special": return skills.special;
                default: throw new ArgumentException("Unknown skill slot: " + slot);
            }
        }

        private static IEnumerator MoveActor(CharacterBody actor, Vector3 end, float duration)
        {
            if (!actor.characterMotor || duration <= 0)
                throw new ArgumentException("An assisted move needs a character motor and positive duration.");
            Vector3 start = actor.transform.position;
            float began = Time.fixedTime;
            while (Time.fixedTime < began + duration)
            {
                actor.characterMotor.Motor.SetPosition(Vector3.Lerp(start, end, (Time.fixedTime - began) / duration));
                yield return new WaitForFixedUpdate();
            }
            actor.characterMotor.Motor.SetPosition(end);
        }

        private void WriteFrame(string image)
        {
            Texture2D screenshot = ScreenCapture.CaptureScreenshotAsTexture();
            try
            {
                File.WriteAllBytes(image, screenshot.EncodeToPNG());
            }
            finally
            {
                Destroy(screenshot);
            }
        }

        private void InstallAudioObserver()
        {
            active = this;
            harmony = new Harmony(PluginId);
            var methods = typeof(AkSoundEngine).GetMethods(BindingFlags.Public | BindingFlags.Static)
                .Where(method => method.Name == "PostEvent" && method.ReturnType == typeof(uint));
            var postfix = new HarmonyMethod(typeof(Recorder), nameof(ObservePostEvent));
            foreach (MethodInfo method in methods)
                harmony.Patch(method, postfix: postfix);
        }

        private static void ObservePostEvent(object[] __args, uint __result)
        {
            if (active == null || __args.Length < 2)
                return;
            var emitter = __args[1] as GameObject;
            active.audio.Add(new AudioEvent
            {
                step = active.stepId,
                frame = Time.frameCount,
                seconds = Time.realtimeSinceStartup,
                event_name = __args[0] as string,
                event_id = __args[0] is uint id ? id.ToString(CultureInfo.InvariantCulture) : null,
                emitter = emitter ? emitter.name : null,
                playing_id = __result.ToString(CultureInfo.InvariantCulture)
            });
        }

        private void Finish(Exception error)
        {
            if (finished)
                return;
            finished = true;
            SteamworksClientManager.onLoaded -= IsolateProfile;
            active = null;
            GrappleObservation.Stop();
            harmony?.UnpatchSelf();
            if (waveRecording)
                waveStatus = AkSoundEngine.StopOutputCapture().ToString();
            if (output != null)
            {
                using (var log = new StreamWriter(Path.Combine(output, "audio-events.jsonl")))
                    foreach (AudioEvent entry in audio)
                        log.WriteLine(JsonUtility.ToJson(entry));
                CaptureEvidence.WriteJson(Path.Combine(output, "result.json"), new RunResult
                {
                    status = error == null ? "passed" : "failed",
                    error = error?.Message,
                    scene = SceneManager.GetActiveScene().name,
                    seed = Run.instance ? Run.instance.seed.ToString(CultureInfo.InvariantCulture) : "",
                    route = request?.scenario.naturalFirstStage == true ? "native-first-stage" : "assisted-direct-entry",
                    steam_build = RoR2Application.steamBuildId,
                    graphics_device = SystemInfo.graphicsDeviceName,
                    graphics_api = SystemInfo.graphicsDeviceVersion,
                    expansions = Run.instance ? ExpansionCatalog.expansionDefs.Where(Run.instance.IsExpansionEnabled)
                        .Select(expansion => expansion.name).ToArray() : Array.Empty<string>(),
                    volume_master = GameConsole.instance?.FindConVar("volume_master")?.GetString(),
                    volume_sfx = GameConsole.instance?.FindConVar("volume_sfx")?.GetString(),
                    volume_music = GameConsole.instance?.FindConVar("volume_music")?.GetString(),
                    audio_capture_status = waveStatus,
                    audio_events = "audio-events.jsonl",
                    steps = steps.ToArray()
                });
            }
            if (error != null)
                Logger.LogError(error);
            Application.Quit(error == null ? 0 : 1);
        }

        private sealed class ReferenceAchievements : AchievementSystem
        {
            public override void AddAchievement(string achievementName) { }
        }

        private sealed class RecordingCamera : ICameraStateProvider
        {
            public CameraState state;
            public float fov;
            public void GetCameraState(CameraRigController rig, ref CameraState result) => result = state;
            public bool IsUserLookAllowed(CameraRigController rig) => false;
            public bool IsUserControlAllowed(CameraRigController rig) => false;
            public bool IsHudAllowed(CameraRigController rig) => true;
        }

        [Serializable]
        private sealed class AudioEvent
        {
            public string step;
            public int frame;
            public float seconds;
            public string event_name;
            public string event_id;
            public string emitter;
            public string playing_id;
        }

        [Serializable]
        private sealed class RunResult
        {
            public string status;
            public string error;
            public string scene;
            public string seed;
            public string route;
            public string steam_build;
            public string graphics_device;
            public string graphics_api;
            public string[] expansions;
            public string volume_master, volume_sfx, volume_music;
            public string audio_capture_status;
            public string audio_events;
            public StepResult[] steps;
        }

        [Serializable]
        private sealed class StepResult
        {
            public string id;
            public string frame;
            public string state;
            public string grapple_ticks;
            public FrameTime[] timeline;
        }

        [Serializable]
        private sealed class FrameTime
        {
            public string frame;
            public float seconds;
        }
    }
}
