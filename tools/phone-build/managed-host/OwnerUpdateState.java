package dev.ror2lab.phonebuildhostfixture;

/** Android-free presentation policy; persisted worker/install facts are authoritative. */
public final class OwnerUpdateState {
    public enum Phase { IDLE, CHECKING, UP_TO_DATE, UPDATE_AVAILABLE, DOWNLOADING, VERIFYING,
        BUILDING, SIGNING, READY, INSTALLING, AWAITING_CONFIRMATION, INSTALLED, INPUT_REQUIRED, VALIDATING, IMPORTING, IMPORTED, PAUSED, CANCELLED, INTERRUPTED, VERIFYING_PROFILE, RECOVERING_PROFILE, RECOVERY_REQUIRED, ERROR }
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
    public static String backendScript(String action) {
        if (action == null) return "repo/tools/phone-build/owner-code/run_android.py";
        if ("release-check".equals(action) || "release-build".equals(action) || "install-prepare".equals(action) || "release-rollback".equals(action)) return "repo/tools/phone-build/owner-apk/updates.py";
        throw new IllegalArgumentException("Unsupported installer action");
    }
    public Phase phase() { return phase; }
    public String message() { return message; }
    public boolean busy() {
        switch (phase) {
            case CHECKING: case VALIDATING: case DOWNLOADING: case VERIFYING: case BUILDING: case SIGNING:
            case INSTALLING: case AWAITING_CONFIRMATION: case VERIFYING_PROFILE: case RECOVERING_PROFILE: return true;
            default: return false;
        }
    }
    public boolean canCheck() { return !busy(); }
    public boolean canBuild() { return phase == Phase.UPDATE_AVAILABLE; }
    public boolean canInstall() { return phase == Phase.READY; }
    public void observe(String state, String detail) {
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
