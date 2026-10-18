// Authored wrapper around the exact editor's native billboard atlas/vertex path.
// Source atlases/dimensions remain; Lambert lighting approximates RoR2's ramp.
Shader "Porting Lab/Android Billboard Presentation" {
 Properties {
  _MainTex("Recovered atlas",2D)="white"{}
  _Color("Recovered tint",Color)=(1,1,1,1)
  _HueVariation("Recovered hue variation",Color)=(1,.5,0,.1)
  [Normal]_BumpMap("Recovered atlas normals",2D)="bump"{}
  _Cutoff("Recovered alpha cutoff",Range(0,1))=.5
  _EmissionOn("Recovered emission switch",Float)=0
  _EmissionTex("Recovered emission",2D)="black"{}
  _EmissionTint("Recovered emission tint",Color)=(0,0,0,0)
 }
 SubShader {
  Tags {"Queue"="AlphaTest" "RenderType"="TransparentCutout" "DisableBatching"="LODFading"}
  Cull Off
  CGPROGRAM
   #pragma target 3.0
   #pragma surface surf Lambert vertex:SpeedTreeBillboardVert addshadow dithercrossfade
   #pragma multi_compile __ EFFECT_BUMP
   #pragma multi_compile __ EFFECT_HUE_VARIATION
   #pragma multi_compile __ BILLBOARD_FACE_CAMERA_POS
   #include "SpeedTreeBillboardCommon.cginc"
   sampler2D _EmissionTex;fixed4 _EmissionTint;float _EmissionOn;
   void surf(Input i,inout SurfaceOutput o){
    SpeedTreeFragOut atlasInputs;SpeedTreeFrag(i,atlasInputs);
    o.Albedo=atlasInputs.Albedo;o.Alpha=atlasInputs.Alpha;
    #ifdef EFFECT_BUMP
     o.Normal=atlasInputs.Normal;
    #endif
    o.Emission=tex2D(_EmissionTex,i.mainTexUV).rgb*_EmissionTint.rgb*saturate(_EmissionOn);
   }
  ENDCG
 }
}
