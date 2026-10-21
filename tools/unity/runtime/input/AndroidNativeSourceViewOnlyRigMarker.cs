// This marker is merged into RoR2.dll so the narrowly patched original
// aim-ray method recognizes only an explicitly bound view-only rig.
using System;
using System.Reflection;
using RoR2;
using UnityEngine;

namespace RoR2
{
    public sealed class AndroidNativeSourceViewOnlyRigMarker : MonoBehaviour
    {
        CameraRigController rig;
        GameObject target;
        ICameraStateProvider ownerProvider;
        Action originalEarlyUpdate;
        bool originalContextReady;
        int originalEarlyUpdatePumpCount;
        static SceneCamera ownedActivationSceneCamera;
        static bool ownedActivationConsoleConfigurationSkipped;

        public int GetOriginalEarlyUpdatePumpCount() => originalEarlyUpdatePumpCount;

        // A single, exact activation token joins the clone's synchronous Unity
        // OnEnable path to SceneCamera's narrowly guarded convar setup. The token
        // is owned only for the SetActive(true) call and never suppresses another camera.
        public static void BeginOwnedSceneCameraActivation(SceneCamera sceneCamera)
        {
            if (!sceneCamera || !ReferenceEquals(ownedActivationSceneCamera, null))
                throw new InvalidOperationException("owned SceneCamera activation is null or already active");
            ownedActivationSceneCamera = sceneCamera;
            ownedActivationConsoleConfigurationSkipped = false;
        }

        public static bool EndOwnedSceneCameraActivation(SceneCamera sceneCamera)
        {
            if (!ReferenceEquals(ownedActivationSceneCamera, sceneCamera))
                throw new InvalidOperationException("owned SceneCamera activation token does not match");
            bool skipped = ownedActivationConsoleConfigurationSkipped;
            ownedActivationSceneCamera = null;
            ownedActivationConsoleConfigurationSkipped = false;
            return skipped;
        }

        public static bool ShouldSkipMissingConsole(SceneCamera sceneCamera, bool consoleAvailable)
        {
            if (consoleAvailable || !sceneCamera || !ReferenceEquals(ownedActivationSceneCamera, sceneCamera))
                return false;
            ownedActivationConsoleConfigurationSkipped = true;
            return true;
        }

        void Awake()
        {
            TryBindOriginalEarlyUpdate();
        }

        bool TryBindOriginalEarlyUpdate()
        {
            if (originalEarlyUpdate != null)
                return true;
            if (!CanPumpOwnedRig())
                return false;
            var callback = typeof(CameraRigController).GetMethod("EarlyUpdate",
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
            if (callback == null || !callback.IsPrivate || callback.IsStatic || callback.ReturnType != typeof(void) ||
                callback.GetParameters().Length != 0)
                throw new InvalidOperationException("accepted CameraRigController.EarlyUpdate method shape changed");
            originalEarlyUpdate = (Action)Delegate.CreateDelegate(typeof(Action), rig, callback);
            return originalEarlyUpdate != null;
        }

        // RoR2 normally calls this through RoR2Application.onUpdate. The composed
        // route intentionally leaves that application inactive, so this component
        // dispatches the original method body for only its one explicitly bound rig.
        // CameraRigController.LateUpdate and all other Unity callbacks remain native.
        void Update()
        {
            TryPumpOriginalEarlyUpdate();
        }

        public bool TryPumpOriginalEarlyUpdate()
        {
            if (!CanPumpOwnedRig() || (originalEarlyUpdate == null && !TryBindOriginalEarlyUpdate()))
            {
                originalContextReady = false;
                return false;
            }
            var application = RoR2Application.instance;
            if (application && application.isActiveAndEnabled)
                return originalContextReady && rig.target == target;
            bool priorContextReady = originalContextReady;
            originalContextReady = false;
            try
            {
                originalEarlyUpdate();
            }
            catch
            {
                originalContextReady = false;
                throw;
            }
            originalEarlyUpdatePumpCount++;
            // The accepted method always assigns target before its time/cutscene
            // guard. It creates CameraModeContext only for a nonzero-time,
            // non-cutscene update. Latch that context after its first real creation;
            // a later zero-time or cutscene frame does not erase a valid context.
            if (rig.target == target && Time.deltaTime > 0f && !rig.isCutscene)
                originalContextReady = true;
            else if (rig.target == target)
                originalContextReady = priorContextReady;
            return originalContextReady;
        }

        public bool IsOriginalUpdateContextReadyFor(CameraRigController candidate, GameObject candidateTarget,
                                                     ICameraStateProvider candidateOwnerProvider)
        {
            return originalContextReady && IsPumpBoundTo(candidate, candidateTarget, candidateOwnerProvider) &&
                   candidate.target == candidateTarget;
        }

        bool CanPumpOwnedRig()
        {
            var ownerBehaviour = ownerProvider as MonoBehaviour;
            return this && rig && target && ownerProvider != null && isActiveAndEnabled &&
                   ReferenceEquals(rig.GetComponent(typeof(AndroidNativeSourceViewOnlyRigMarker)), this) &&
                   rig.isActiveAndEnabled && rig.gameObject.activeInHierarchy &&
                   rig.localUserViewer == null && rig.nextTarget == target && ownerBehaviour &&
                   ownerBehaviour.isActiveAndEnabled && ownerBehaviour.gameObject == rig.gameObject;
        }

        bool IsPumpBoundTo(CameraRigController candidate, GameObject candidateTarget,
                           ICameraStateProvider candidateOwnerProvider)
        {
            return CanPumpOwnedRig() && candidate && candidateTarget && candidate == rig &&
                   candidateTarget == target && candidateOwnerProvider != null &&
                   candidateOwnerProvider == ownerProvider && candidate.localUserViewer == null &&
                   candidate.nextTarget == candidateTarget;
        }

        public void Bind(CameraRigController sourceRig, GameObject sourceTarget,
                         ICameraStateProvider sourceOwnerProvider)
        {
            if (!sourceRig || !sourceTarget || sourceOwnerProvider == null || rig || target || ownerProvider != null)
                throw new InvalidOperationException("view-only rig marker is already bound or lacks exact ownership inputs");
            rig = sourceRig;
            target = sourceTarget;
            ownerProvider = sourceOwnerProvider;
        }

        public bool IsBoundTo(CameraRigController candidate, GameObject candidateTarget,
                              ICameraStateProvider candidateOwnerProvider)
        {
            var ownerBehaviour = ownerProvider as MonoBehaviour;
            return this && isActiveAndEnabled && candidate && candidateTarget &&
                   rig == candidate && target == candidateTarget && ownerProvider != null &&
                   ownerBehaviour && ownerBehaviour.isActiveAndEnabled &&
                   ownerBehaviour.gameObject == candidate.gameObject &&
                   ownerProvider == candidateOwnerProvider && candidate.localUserViewer == null &&
                   candidate.target == candidateTarget;
        }

        public static bool ShouldSkipNullViewerAim(CameraRigController candidate, GameObject candidateTarget)
        {
            if (!candidate || !candidateTarget || candidate.localUserViewer != null || candidate.target != candidateTarget)
                return false;
            var marker = candidate.GetComponent(typeof(AndroidNativeSourceViewOnlyRigMarker)) as AndroidNativeSourceViewOnlyRigMarker;
            return marker && marker.IsBoundTo(candidate, candidateTarget, marker.ownerProvider);
        }
    }
}
