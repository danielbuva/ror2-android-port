Shader "Porting Lab/Android Distortion Presentation" {
 Properties {
  [Normal]_BumpMap("Source bump",2D)="bump"{} _MaskTex("Source mask",2D)="white"{} _AndroidMaskEnabled("Mask present",Float)=0
  _Magnitude("Source magnitude",Float)=0 _InvFade("Source soft factor",Float)=1
  _NearFadeZeroDistance("Source near zero",Float)=0 _NearFadeOneDistance("Source near one",Float)=1
  _FarFadeOneDistance("Source far one",Float)=200000 _FarFadeZeroDistance("Source far zero",Float)=250000
  _DistanceModulationOn("Source distance modulation",Float)=0 _DistanceModulationMagnitude("Source modulation magnitude",Float)=0
 }
 SubShader {
  Tags{"Queue"="Transparent+2000" "RenderType"="Transparent" "IgnoreProjector"="True"} Cull Off ZWrite Off ZTest LEqual
  // Same named-grab boundary as the source. Offset/distance response is approximate.
  GrabPass{"_GrabTexturePostProcess"}
  Pass{Blend One Zero CGPROGRAM
   #pragma target 3.0
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _BumpMap,_MaskTex,_GrabTexturePostProcess;float4 _BumpMap_ST,_MaskTex_ST,_GrabTexturePostProcess_TexelSize;
   UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
   float _Magnitude,_InvFade,_NearFadeZeroDistance,_NearFadeOneDistance,_FarFadeOneDistance,_FarFadeZeroDistance,_DistanceModulationOn,_DistanceModulationMagnitude,_AndroidMaskEnabled;
   struct appdata{float4 vertex:POSITION;float2 uv:TEXCOORD0;fixed4 color:COLOR;};
   struct v2f{float4 pos:SV_POSITION;float2 uv:TEXCOORD0;float4 grab:TEXCOORD1;float4 screen:TEXCOORD2;float3 world:TEXCOORD3;float eye:TEXCOORD4;fixed alpha:COLOR;};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.grab=ComputeGrabScreenPos(o.pos);o.screen=ComputeScreenPos(o.pos);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.eye=-UnityObjectToViewPos(v.vertex).z;o.alpha=v.color.a;return o;}
   half4 frag(v2f i):SV_Target{
    float distance=length(_WorldSpaceCameraPos-i.world);
    float nearFade=saturate((distance-_NearFadeZeroDistance)/max(_NearFadeOneDistance-_NearFadeZeroDistance,.0001));
    float farFade=saturate((_FarFadeZeroDistance-distance)/max(_FarFadeZeroDistance-_FarFadeOneDistance,.0001));
    float depth=LinearEyeDepth(SAMPLE_DEPTH_TEXTURE_PROJ(_CameraDepthTexture,UNITY_PROJ_COORD(i.screen)));
    float fade=nearFade*farFade*saturate((depth-i.eye)*_InvFade)*i.alpha;
    if(_AndroidMaskEnabled>.5)fade*=tex2D(_MaskTex,i.uv*_MaskTex_ST.xy+_MaskTex_ST.zw).a;
    if(_DistanceModulationOn>.5)fade*=pow(max(distance,.0001),-_DistanceModulationMagnitude);
    float2 offset=UnpackNormal(tex2D(_BumpMap,i.uv*_BumpMap_ST.xy+_BumpMap_ST.zw)).xy*_Magnitude*fade;
    i.grab.xy+=offset*_GrabTexturePostProcess_TexelSize.xy*i.grab.w;
    return tex2Dproj(_GrabTexturePostProcess,UNITY_PROJ_COORD(i.grab));
   }
  ENDCG}
 }
}
