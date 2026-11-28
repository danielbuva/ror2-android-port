package dev.ror2lab.phonebuildhostfixture;

/** Android-free presentation policy; persisted worker/install facts are authoritative. */
public final class OwnerUpdateState {
    public enum Phase { IDLE, CHECKING, UP_TO_DATE, UPDATE_AVAILABLE, DOWNLOADING, VERIFYING,
        BUILDING, SIGNING, READY, INSTALLING, AWAITING_CONFIRMATION, INSTALLED, INPUT_REQUIRED, VALIDATING, IMPORTING, IMPORTED,
        ACQUIRING_TOOLS, TOOLS_READY, TOOLS_UNAVAILABLE, PAUSED, CANCELLED, INTERRUPTED, VERIFYING_PROFILE, RECOVERING_PROFILE, REMOVING_MISPLACED, RECOVERY_REQUIRED, ERROR }
    private Phase phase = Phase.IDLE;
    private String message = "Check for a signed public release.";
    /** Presentation only: preserve accessibility quiet time between live-detail updates. */
    public static final class StatusRender {
        private String text;
        private Phase phase;
        private long renderedAt;
        public boolean update(String nextText, Phase nextPhase, long elapsedMillis) {
            if (nextText.equals(text)) return false;
            // State transitions remain immediate; continuously changing details
            // coalesce to the latest observation, without slowing worker sampling.
            if (phase == nextPhase && elapsedMillis - renderedAt < 2000) return false;
            text = nextText;
            phase = nextPhase;
            renderedAt = elapsedMillis;
            return true;
        }
    }
    /** Presentation only; absent timestamps/counts never imply progress. */
    public static long liveSeconds(boolean running, String status, boolean paused, long updatedAt, long now) {
        if (!running || !"running".equals(status) || paused || updatedAt <= 0 || now < updatedAt) return 0;
        return now - updatedAt;
    }
    public static String stageProgress(String status, long completed, long total) {
        if ("not_required".equals(status)) return "not required";
        if (total <= 0 || completed < 0 || completed > total) return "progress unavailable";
        return completed + "/" + total;
    }
    /** Never imply a comparison against an installed release without its matching receipt. */
    public static String releaseChanges(boolean installedKnown, int changed, int removed) {
        if (!installedKnown || changed < 0 || removed < 0) return "Installed release comparison unavailable.";
        return "Changed outputs: " + changed + "; removed: " + removed;
    }
    public static String failureDetail(String stage, String reason) {
        return "First failure: " + stage + " — " + reason + ". Retry revalidates retained work; this is not installation success.";
    }
    public static String backendScript(String action) {
        if (action == null) return "repo/tools/phone-build/owner-code/run_android.py";
        if ("release-check".equals(action) || "release-build".equals(action) || "install-prepare".equals(action) || "release-rollback".equals(action)) return "repo/tools/phone-build/owner-apk/updates.py";
        throw new IllegalArgumentException("Unsupported installer action");
    }
    /** A fresh screen snapshot uses observed owners, never remembered button state. */
    public static final class Screen {
        public final boolean check, build, install, prepare, selectInputs, importInputs, pause, resume, cancel, retry, recover, rollback;
        public final String text;
        private Screen(OwnerUpdateState model, boolean running, boolean installing, boolean pendingRecovery,
                       boolean inputsAvailable, String importState, boolean rollbackAvailable, boolean resumable, boolean liveControls) {
            boolean idle = !running && !installing && !pendingRecovery;
            check = idle && model.canCheck();
            build = idle && (model.canBuild() || "IMPORTED".equals(importState));
            install = idle && model.canInstall();
            prepare = idle; selectInputs = idle; importInputs = idle && inputsAvailable;
            pause = running && liveControls && !installing && !pendingRecovery;
            cancel = pause;
            resume = !installing && !pendingRecovery && (running ? liveControls : (resumable &&
                (model.phase == Phase.PAUSED || model.phase == Phase.INTERRUPTED || model.phase == Phase.CANCELLED)));
            retry = idle && (model.phase == Phase.ERROR || model.phase == Phase.TOOLS_UNAVAILABLE) && resumable;
            recover = !running && !installing && pendingRecovery;
            rollback = idle && rollbackAvailable;
            String next = recover ? "Recover and verify retained profile/settings before another operation."
                : installing ? "Finish Android confirmation or verification; no second installation will start."
                : install ? "Tap Install for the verified build and Android consent."
                : retry ? "Retry revalidates retained work; it does not certify installation."
                : resume && !running ? "Resume revalidates retained work; a ready build may continue to Android installation."
                : build ? "Build locally from admitted inputs; Android installation may follow reconstruction." : "";
            text = (model.phase == Phase.ERROR ? "FAILED" : model.phase.toString().replace('_', ' ')) + "\n" + model.message + (next.isEmpty() ? "" : "\n" + next);
        }
    }
    public Screen screen(boolean running, boolean installing, boolean pendingRecovery, boolean inputsAvailable,
                         String importState, boolean rollbackAvailable, boolean resumable, boolean liveControls) {
        return new Screen(this, running, installing, pendingRecovery, inputsAvailable, importState, rollbackAvailable, resumable, liveControls);
    }
    static boolean requiresInstallPermission(String action) {
        return "release-build".equals(action) || "release-rollback".equals(action) || "install".equals(action);
    }

    public static boolean resumableAction(String action) {
        return "import".equals(action) || "tool-acquire".equals(action) || "release-build".equals(action) || "release-rollback".equals(action)
            || "install-prepare".equals(action) || "release-check".equals(action);
    }
    /** Shared Activity/notification explanation, never a thermal control policy. */
    public static String backgroundDetail(boolean running, boolean fresh, String status, boolean manual, boolean thermal, String error) {
        if ("cancelled".equals(status)) return (!running || !fresh ? "Last recorded thermal state; not live. " : "")
            + "Conversion cancelled. Retained work is revalidated on explicit retry.";
        if (!running || !fresh) return "Last recorded thermal state; not live. "
            + (error != null && !error.isEmpty() ? "Recorded failure: " + error : "Reopen progress for current worker status.");
        if (error != null && !error.isEmpty()) return "Conversion stopped or unavailable: " + error + ". Retry only after resolving the reported cause.";
        if ("failed".equals(status)) return "Conversion failed. Review the first failure before retrying.";
        if ("complete".equals(status)) return "Producer finished; later reconstruction or installation steps may remain.";
        if (thermal || "cooling".equals(status)) return (manual ? "Paused by you and cooling. " : "Cooling automatically. ")
            + "Resume clears only a manual pause; it cannot bypass cooling. The 90 C ceiling releases below 70 C; the normal duty gate must also clear. A 15-minute ceiling pause stops work.";
        if (manual || "paused".equals(status)) return "Paused by you; monitoring remains active. Resume continues when thermal admission permits.";
        return "Conversion active in the foreground service. You may leave this screen; reopen it to inspect progress or cancel.";
    }
    public Phase phase() { return phase; }
    public String message() { return message; }
    public boolean busy() {
        switch (phase) {
            case CHECKING: case VALIDATING: case ACQUIRING_TOOLS: case DOWNLOADING: case VERIFYING: case BUILDING: case SIGNING:
            case INSTALLING: case AWAITING_CONFIRMATION: case VERIFYING_PROFILE: case RECOVERING_PROFILE: case REMOVING_MISPLACED: return true;
            default: return false;
        }
    }
    public boolean canCheck() { return !busy(); }
    public boolean canBuild() { return phase == Phase.UPDATE_AVAILABLE; }
    public boolean canInstall() { return phase == Phase.READY; }
    public void observe(String state, String detail) {
        if ("INPUTS_REQUIRED".equals(state)) state = Phase.INPUT_REQUIRED.name();
        try { phase = Phase.valueOf(state); }
        catch (RuntimeException unknown) { phase = Phase.ERROR; detail = "Unsupported update state: " + state; }
        message = detail == null ? phase.toString() : detail;
    }
    public void beginCheck() {
        if (!canCheck()) throw new IllegalStateException("An update operation is already active");
        observe("CHECKING", "Checking signed release metadata…");
    }
    public void beginBuild() {
        if (!canBuild()) throw new IllegalStateException("Check for a newer release first");
        observe("DOWNLOADING", "Downloading public tools; original game data stays on this device…");
    }
    public void beginInstall() {
        if (!canInstall()) throw new IllegalStateException("A verified owner build is required");
        observe("INSTALLING", "Installing the verified owner build in place…");
    }
}
