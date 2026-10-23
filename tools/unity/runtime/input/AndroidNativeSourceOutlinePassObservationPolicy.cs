using System;
using System.Reflection;

// Pure identity/metadata contract called by AndroidNativeSourceCameraRigOwner.
// It contains no Unity calls so the selection guard can be exercised with fakes.
internal static class AndroidNativeSourceOutlinePassObservationPolicy
{
    internal const string ExpectedShaderName = "Hopoo Games/Internal/Outline Highlight";
    internal const int RequiredSourcePassIndex = 1;
    internal const int AcceptedSourcePassCount = 2;
    internal const int MaxFailureTypeChars = 96;
    internal const int MaxShaderNameChars = 128;

    internal static bool ShouldCapture(bool requested, bool alreadyCaptured,
        object callbackCamera, object ownedCamera,
        object callbackOutline, object ownedOutline,
        object callbackSceneCamera, object ownedSceneCamera,
        object callbackRig, object ownedRig)
    {
        return requested && !alreadyCaptured && callbackCamera != null &&
            ReferenceEquals(callbackCamera, ownedCamera) &&
            callbackOutline != null && ReferenceEquals(callbackOutline, ownedOutline) &&
            callbackSceneCamera != null && ReferenceEquals(callbackSceneCamera, ownedSceneCamera) &&
            callbackRig != null && ReferenceEquals(callbackRig, ownedRig);
    }

    internal static bool HasExactMaterialField(FieldInfo field, Type outlineType, Type materialType)
    {
        return field != null && outlineType != null && materialType != null &&
            field.DeclaringType == outlineType && field.FieldType == materialType &&
            !field.IsStatic && field.IsPrivate;
    }

    internal static string BoundedFailureType(Exception exception)
    {
        string value = exception == null ? "unknown" : exception.GetType().Name;
        return value.Length <= MaxFailureTypeChars ? value : value.Substring(0, MaxFailureTypeChars);
    }

    internal static string BoundedShaderName(string value)
    {
        value = value ?? string.Empty;
        return value.Length <= MaxShaderNameChars ? value : value.Substring(0, MaxShaderNameChars);
    }
}
