using System;
using System.Linq;
using Mono.Cecil;
using Mono.Cecil.Cil;

internal static class VerifyCameraGuardPatch
{
    static string OperandKey(Instruction instruction, Func<Instruction, int> index)
    {
        object operand = instruction.Operand;
        if (operand == null) return "";
        if (operand is Instruction branch) return "->" + index(branch);
        if (operand is Instruction[] branches) return "->" + String.Join(",", branches.Select(index));
        if (operand is MethodReference method) return method.FullName;
        if (operand is FieldReference field) return field.FullName;
        if (operand is TypeReference type) return type.FullName;
        if (operand is VariableDefinition variable) return "v" + variable.Index;
        if (operand is ParameterDefinition parameter) return "p" + parameter.Index;
        return Convert.ToString(operand, System.Globalization.CultureInfo.InvariantCulture);
    }

    static string[] BodyKey(MethodDefinition method, Func<int, bool> skip = null)
    {
        var kept = method.Body.Instructions.Select((instruction, originalIndex) => new { instruction, originalIndex })
            .Where(x => skip == null || !skip(x.originalIndex)).Select(x => x.instruction).ToArray();
        var indexes = kept.Select((instruction, index) => new { instruction, index }).ToDictionary(x => x.instruction, x => x.index);
        return kept.Select(x => x.OpCode.Code + " " + OperandKey(x, target => indexes[target])).ToArray();
    }

    static void Require(bool condition, string reason)
    {
        if (!condition) throw new InvalidOperationException(reason);
    }

    static int Main(string[] args)
    {
        if (args.Length != 2) return 2;
        using (var before = ModuleDefinition.ReadModule(args[0]))
        using (var after = ModuleDefinition.ReadModule(args[1]))
        {
            Require(before.Assembly.Name.Name == after.Assembly.Name.Name &&
                    before.Assembly.Name.Version.ToString() == after.Assembly.Name.Version.ToString(), "assembly identity changed");
            var oldNames = before.Types.Select(x => x.FullName).ToArray();
            var newNames = after.Types.Select(x => x.FullName).ToArray();
            Require(newNames.Length == oldNames.Length + 1 && oldNames.All(newNames.Contains), "unexpected type addition/removal");
            Require(newNames.Count(x => x == "RoR2.AndroidNativeSourceViewOnlyRigMarker") == 1, "marker type not unique");
            var targetName = "RoR2.CameraRigController";
            foreach (var oldType in before.Types)
            {
                var newType = after.GetType(oldType.FullName);
                Require(newType != null, "existing type missing " + oldType.FullName);
                Require(oldType.Fields.Select(x => x.FullName).SequenceEqual(newType.Fields.Select(x => x.FullName)), "field set changed " + oldType.FullName);
                Require(oldType.Methods.Select(x => x.FullName).SequenceEqual(newType.Methods.Select(x => x.FullName)), "method set changed " + oldType.FullName);
                foreach (var oldMethod in oldType.Methods)
                {
                    var newMethod = newType.Methods.Single(x => x.FullName == oldMethod.FullName);
                    if (!oldMethod.HasBody) { Require(!newMethod.HasBody, "body added " + oldMethod.FullName); continue; }
                    Require(newMethod.HasBody, "body removed " + oldMethod.FullName);
                    bool aimTarget = oldType.FullName == targetName && oldMethod.Name == "ModifyAimRayIfApplicable";
                    bool sceneCameraTarget = oldType.FullName == "RoR2.SceneCamera" && oldMethod.Name == "ConfigureGraphicsSettings";
                    if (!aimTarget && !sceneCameraTarget)
                        Require(BodyKey(oldMethod).SequenceEqual(BodyKey(newMethod)), "unrelated body changed " + oldMethod.FullName);
                }
            }
            var oldTarget = before.GetType(targetName).Methods.Single(x => x.Name == "ModifyAimRayIfApplicable");
            var newTarget = after.GetType(targetName).Methods.Single(x => x.Name == "ModifyAimRayIfApplicable");
            int helperCall = Array.FindIndex(newTarget.Body.Instructions.ToArray(), x => x.OpCode == OpCodes.Call &&
                x.Operand is MethodReference m && m.FullName == "System.Boolean RoR2.AndroidNativeSourceViewOnlyRigMarker::ShouldSkipNullViewerAim(RoR2.CameraRigController,UnityEngine.GameObject)");
            Require(helperCall >= 2 && helperCall + 1 < newTarget.Body.Instructions.Count, "guard call absent or misplaced");
            Require(newTarget.Body.Instructions[helperCall - 2].OpCode == OpCodes.Ldloc_2 &&
                    newTarget.Body.Instructions[helperCall - 1].OpCode == OpCodes.Ldarg_1 &&
                    newTarget.Body.Instructions[helperCall + 1].OpCode == OpCodes.Brtrue, "guard argument/branch contract changed");
            var branchTarget = (Instruction)newTarget.Body.Instructions[helperCall + 1].Operand;
            Require(branchTarget.OpCode == OpCodes.Ldloc_1 && branchTarget.Next != null && branchTarget.Next.OpCode == OpCodes.Ldc_I4_1,
                    "guard must skip only this rig and continue the original registry scan");
            Require(newTarget.Body.Instructions.Count == oldTarget.Body.Instructions.Count + 4, "target method change is not the exact four-instruction guard");
            var skip = newTarget.Body.Instructions.Select((x, i) => new { x, i }).Where(x => x.x.OpCode == OpCodes.Call &&
                x.x.Operand is MethodReference m && m.Name == "ShouldSkipNullViewerAim").Select(x => x.i).Single();
            Require(BodyKey(oldTarget).SequenceEqual(BodyKey(newTarget, i => i >= skip - 2 && i <= skip + 1)),
                    "original target method instructions changed outside the guard");
            var oldScene = before.GetType("RoR2.SceneCamera").Methods.Single(x => x.Name == "ConfigureGraphicsSettings");
            var newScene = after.GetType("RoR2.SceneCamera").Methods.Single(x => x.Name == "ConfigureGraphicsSettings");
            var sceneInstructions = newScene.Body.Instructions.ToArray();
            int sceneGuardCall = Array.FindIndex(sceneInstructions, x => x.OpCode == OpCodes.Call &&
                x.Operand is MethodReference m && m.FullName == "System.Boolean RoR2.AndroidNativeSourceViewOnlyRigMarker::ShouldSkipMissingConsole(RoR2.SceneCamera,System.Boolean)");
            Require(sceneGuardCall == 4 && sceneInstructions.Length == oldScene.Body.Instructions.Count + 7,
                    "SceneCamera guard is absent or not the exact seven-instruction entry gate");
            Require(sceneInstructions[0].OpCode == OpCodes.Ldarg_0 &&
                    sceneInstructions[1].OpCode == OpCodes.Call && sceneInstructions[1].Operand is MethodReference console &&
                    console.FullName == "RoR2.Console RoR2.Console::get_instance()" &&
                    sceneInstructions[2].OpCode == OpCodes.Ldnull && sceneInstructions[3].OpCode == OpCodes.Cgt_Un &&
                    sceneInstructions[5].OpCode == OpCodes.Brfalse && sceneInstructions[6].OpCode == OpCodes.Ret &&
                    ReferenceEquals(sceneInstructions[5].Operand, sceneInstructions[7]),
                    "SceneCamera guard does not preserve the original entry on Console-present/other-camera paths");
            Require(BodyKey(oldScene).SequenceEqual(BodyKey(newScene, i => i < 7)),
                    "original SceneCamera configuration body changed outside the guard");
            var marker = after.GetType("RoR2.AndroidNativeSourceViewOnlyRigMarker");
            Require(marker != null && !marker.HasProperties && !marker.HasEvents &&
                    marker.Methods.Any(x => x.Name == "Bind") &&
                    marker.Methods.Any(x => x.Name == "IsBoundTo") &&
                    marker.Methods.Any(x => x.Name == "ShouldSkipNullViewerAim") &&
                    marker.Methods.Any(x => x.Name == "GetOriginalEarlyUpdatePumpCount") &&
                    marker.Methods.Any(x => x.Name == "BeginOwnedSceneCameraActivation") &&
                    marker.Methods.Any(x => x.Name == "EndOwnedSceneCameraActivation") &&
                    marker.Methods.Any(x => x.Name == "ShouldSkipMissingConsole"),
                    "marker methods or copier-compatible type shape incomplete");
            var update = marker.Methods.Single(x => x.Name == "Update");
            var pump = marker.Methods.Single(x => x.Name == "TryPumpOriginalEarlyUpdate");
            var contextReady = marker.Methods.Single(x => x.Name == "IsOriginalUpdateContextReadyFor");
            Require(update.IsPrivate && !update.IsStatic && update.ReturnType.FullName == "System.Void" &&
                    update.Parameters.Count == 0 && update.HasBody, "Unity Update pump callback signature changed");
            Require(pump.IsPublic && !pump.IsStatic && pump.ReturnType.FullName == "System.Boolean" &&
                    pump.Parameters.Count == 0 && pump.HasBody, "manual original update pump signature changed");
            Require(contextReady.IsPublic && !contextReady.IsStatic && contextReady.ReturnType.FullName == "System.Boolean" &&
                    contextReady.Parameters.Count == 3 && contextReady.Parameters[0].ParameterType.FullName == "RoR2.CameraRigController" &&
                    contextReady.Parameters[1].ParameterType.FullName == "UnityEngine.GameObject" &&
                    contextReady.Parameters[2].ParameterType.FullName == "RoR2.ICameraStateProvider", "context readiness contract changed");
            Require(update.Body.Instructions.Count(x => x.OpCode == OpCodes.Call &&
                    x.Operand is MethodReference m && m.Name == "TryPumpOriginalEarlyUpdate") == 1,
                    "Unity Update must dispatch exactly one bounded pump");
            Require(pump.Body.Instructions.Count(x => x.OpCode == OpCodes.Callvirt &&
                    x.Operand is MethodReference m && m.FullName == "System.Void System.Action::Invoke()") == 1,
                    "pump must invoke only the cached original callback delegate");
            Require(pump.Body.Instructions.Any(x => x.Operand is MethodReference m &&
                    m.FullName == "RoR2.RoR2Application RoR2.RoR2Application::get_instance()") &&
                    pump.Body.Instructions.Any(x => x.Operand is MethodReference m &&
                    m.FullName == "System.Boolean UnityEngine.Behaviour::get_isActiveAndEnabled()"),
                    "pump must refuse while original application updates are active");
            var beforeRefs = before.AssemblyReferences.Select(x => x.FullName).OrderBy(x => x).ToArray();
            var afterRefs = after.AssemblyReferences.Select(x => x.FullName).OrderBy(x => x).ToArray();
            if (!beforeRefs.SequenceEqual(afterRefs))
            {
                Console.WriteLine("before_refs=" + String.Join("|", beforeRefs));
                Console.WriteLine("after_refs=" + String.Join("|", afterRefs));
                throw new InvalidOperationException("assembly references changed");
            }
            Console.WriteLine("existing_types=" + oldNames.Length + " aim_original_instructions=" + oldTarget.Body.Instructions.Count +
                              " aim_new_instructions=" + newTarget.Body.Instructions.Count + " scene_original_instructions=" + oldScene.Body.Instructions.Count +
                              " scene_new_instructions=" + newScene.Body.Instructions.Count + " unrelated_bodies_unchanged=true");
        }
        return 0;
    }
}
