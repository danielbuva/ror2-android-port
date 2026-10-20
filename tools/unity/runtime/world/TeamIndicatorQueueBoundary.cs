// Subsystem: UI/position indicators. Owner map: docs/ARCHITECTURE.md#ownership.
// Setup: native TeamComponent team/model lifecycle; dispatch: AutomaticDirectorBoundary.FixedUpdate;
// teardown: native TeamComponent.OnDestroy/OnDeathStart, then J787 completed-session pruning.
using System;
using System.Reflection;
using RoR2;
using UnityEngine;

public sealed partial class PortSession
{
    TeamIndicatorQueueSession teamIndicatorQueueSession;

    TeamIndicatorQueueSession GetTeamIndicatorQueueSession()
    {
        if (teamIndicatorQueueSession == null)
            teamIndicatorQueueSession = new TeamIndicatorQueueSession(this);
        return teamIndicatorQueueSession;
    }

    void TickTeamIndicatorQueue()
    {
        GetTeamIndicatorQueueSession().FixedUpdate();
    }

    // The port owns a Unity fixed tick while RoR2Application's native dispatcher is
    // inactive. The native processor remains the sole queue consumer.
    internal static bool DispatchOriginalIndicatorQueueOnce(bool nativeApplicationActive, bool sessionFailed, Action dispatch,
                                                            Action<Exception> recordFailure, ref Exception firstFailure)
    {
        if (nativeApplicationActive || sessionFailed || firstFailure != null)
            return false;
        try
        {
            dispatch();
            return true;
        }
        catch (Exception error)
        {
            firstFailure = error;
            if (recordFailure != null)
                recordFailure(error);
            return false;
        }
    }

    sealed class TeamIndicatorQueueSession
    {
        readonly PortSession coordinator;
        Action processIndicatorSetupRequests;
        Exception firstFailure;

        public TeamIndicatorQueueSession(PortSession coordinator)
        {
            this.coordinator = coordinator;
        }

        public void FixedUpdate()
        {
            if (coordinator.r == null)
                return;
            var nativeApplication = RoR2Application.instance;
            DispatchOriginalIndicatorQueueOnce(
                nativeApplication && nativeApplication.isActiveAndEnabled, !string.IsNullOrEmpty(coordinator.r.firstFailure),
                () =>
                {
                    if (processIndicatorSetupRequests == null)
                    {
                        var method =
                            typeof(TeamComponent).GetMethod("ProcessIndicatorSetupRequests", BindingFlags.Static | BindingFlags.NonPublic);
                        coordinator.Check(method != null && method.ReturnType == typeof(void) && method.GetParameters().Length == 0,
                                          "Original TeamComponent indicator queue processor changed");
                        processIndicatorSetupRequests = (Action)Delegate.CreateDelegate(typeof(Action), method);
                    }
                    processIndicatorSetupRequests();
                },
                error =>
                {
                    RecordPrimarySessionFailure(coordinator.r, error);
                    try
                    {
                        coordinator.Save();
                    }
                    catch (Exception)
                    { /* Preserve the dispatch failure. */
                    }
                },
                ref firstFailure);
        }
    }
}
