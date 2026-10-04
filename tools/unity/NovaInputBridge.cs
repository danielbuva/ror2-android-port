using System;
using System.Linq;
using RoR2;
using UnityEngine;

// Temporary, removable Nova input producer. No motor, transform, state or skill execution here.
[DefaultExecutionOrder(-20000)]
public sealed class NovaInputBridge : MonoBehaviour {
 [Serializable] public class Mapping {
  public string attempt,observation;
  public int moveX,moveY,aimX,aimY,jump,primary,secondary,utility,special,interact;
  public float moveYSign,aimYSign;
  public bool enableSkills,enableInteraction;
  public void Validate(string expected){
   if(attempt!=expected||string.IsNullOrEmpty(observation))throw new Exception("Unmeasured or stale Nova mapping");
   var axes=new[]{moveX,moveY,aimX,aimY};var buttons=new[]{jump,primary,secondary,utility,special};
   if(axes.Any(x=>x<0||x>=16)||axes.Distinct().Count()!=4||buttons.Any(x=>x<0||x>=20)||buttons.Distinct().Count()!=5||Mathf.Abs(moveYSign)!=1||Mathf.Abs(aimYSign)!=1)throw new Exception("Invalid Nova bindings");
   if(enableInteraction&&(interact<0||interact>=20||buttons.Contains(interact)))throw new Exception("Invalid measured interaction binding");
  }
 }
 [Serializable] public class Raw {public float[] axes=new float[16];public bool[] buttons=new bool[20];}
 public InputBankTest bank;public Mapping mapping;public string error;
 public NovaThirdPersonView thirdPerson;
 public bool enablePrimary,enableAllSkills,diagnosticInput;public bool diagnosticPrimary,diagnosticSecondary,diagnosticUtility,diagnosticSpecial,diagnosticInteract;public Vector3 diagnosticAim;public Vector2 movement,aim;public int fixedTicks,jumpPresses,aimTicks;
 bool focused=true,jumpHeld,jumpLatched;
 public static void RequireNova(){
#if UNITY_ANDROID && !UNITY_EDITOR
  using(var build=new AndroidJavaClass("android.os.Build"))if(build.GetStatic<string>("MODEL")!="Retroid Pocket Nova")throw new Exception("This bridge is authorized only for Nova");
#else
  throw new Exception("Nova physical input requires the Android device");
#endif
  var names=UnityEngine.Input.GetJoystickNames();
  if(names.Length==0||string.IsNullOrEmpty(names[0])||names.Count(x=>!string.IsNullOrEmpty(x))!=1)throw new Exception("Require one controller in Unity joystick slot 1");
 }
 public static Raw ReadRaw(){
  var raw=new Raw();for(int i=0;i<raw.axes.Length;i++)raw.axes[i]=UnityEngine.Input.GetAxisRaw("NovaLabAxis"+i);
  for(int i=0;i<raw.buttons.Length;i++)raw.buttons[i]=UnityEngine.Input.GetKey((KeyCode)((int)KeyCode.Joystick1Button0+i));return raw;
 }
 static Vector2 Stick(Raw raw,int x,int y,float sign){var v=new Vector2(raw.axes[x],raw.axes[y]*sign);float n=v.magnitude;return n<=.18f?Vector2.zero:v/n*Mathf.Min(1,(n-.18f)/.82f);}
 void Update(){
  try{
   if(!bank||mapping==null||!focused){Neutral();return;}
   RequireNova();if(diagnosticInput)return;var raw=ReadRaw();movement=Stick(raw,mapping.moveX,mapping.moveY,mapping.moveYSign);aim=Stick(raw,mapping.aimX,mapping.aimY,mapping.aimYSign);if(thirdPerson!=null)thirdPerson.Look(aim);
   bool down=raw.buttons[mapping.jump];jumpLatched|=down&&!jumpHeld;jumpHeld=down;
  }catch(Exception e){error=e.ToString();enabled=false;Neutral();}
 }
 void FixedUpdate(){
  if(!bank||mapping==null||!focused)return;
  bank.moveVector=thirdPerson!=null&&!diagnosticInput?thirdPerson.Movement(movement):new Vector3(movement.x,0,movement.y);bank.SetRawMoveStates(movement);
  if(diagnosticInput&&diagnosticAim.sqrMagnitude>0){bank.aimDirection=diagnosticAim;aimTicks++;}
  else if(thirdPerson!=null&&!diagnosticInput){bank.aimDirection=thirdPerson.Aim();aimTicks++;thirdPerson.report.maxAimError=Mathf.Max(thirdPerson.report.maxAimError,Vector3.Angle(bank.aimDirection,thirdPerson.report.direction));}
  else if(aim.sqrMagnitude>0){bank.aimDirection=new Vector3(aim.x,0,aim.y);aimTicks++;}
  bank.jump.PushState(jumpHeld||jumpLatched);if(bank.jump.justPressed)jumpPresses++;jumpLatched=false;
  var raw=ReadRaw();bank.interact.PushState(diagnosticInput?diagnosticInteract:mapping.enableInteraction&&raw.buttons[mapping.interact]);bool all=mapping.enableSkills||enableAllSkills;
  bank.skill1.PushState(diagnosticInput?diagnosticPrimary:(all||enablePrimary)&&raw.buttons[mapping.primary]);bank.skill2.PushState(diagnosticInput?diagnosticSecondary:all&&raw.buttons[mapping.secondary]);bank.skill3.PushState(diagnosticInput?diagnosticUtility:all&&raw.buttons[mapping.utility]);bank.skill4.PushState(diagnosticInput?diagnosticSpecial:all&&raw.buttons[mapping.special]);fixedTicks++;
 }
 public void DiagnosticJump(bool down){jumpLatched|=down&&!jumpHeld;jumpHeld=down;}
 public void Neutral(){movement=aim=Vector2.zero;jumpHeld=jumpLatched=false;if(!bank)return;bank.moveVector=Vector3.zero;bank.SetRawMoveStates(Vector2.zero);bank.jump.PushState(false);bank.skill1.PushState(false);bank.skill2.PushState(false);bank.skill3.PushState(false);bank.skill4.PushState(false);bank.interact.PushState(false);}
 void OnApplicationFocus(bool value){focused=value;if(!value)Neutral();}
 void OnApplicationPause(bool value){focused=!value;if(value)Neutral();}
 void OnDisable(){Neutral();}
}
