// This marker is merged into RoR2.dll so the narrowly patched original
// aim-ray method recognizes only an explicitly bound view-only rig.
using RoR2;
using UnityEngine;

namespace RoR2
{
    public sealed class AndroidNativeSourceViewOnlyRigMarker : MonoBehaviour
    {
        CameraRigController rig;
        GameObject target;
        ICameraStateProvider ownerProvider;

        public void Bind(CameraRigController sourceRig, GameObject sourceTarget,
                         ICameraStateProvider sourceOwnerProvider)
        {
            if (!sourceRig || !sourceTarget || sourceOwnerProvider == null || rig || target || ownerProvider != null)
                throw new System.InvalidOperationException("view-only rig marker is already bound or lacks exact ownership inputs");
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
