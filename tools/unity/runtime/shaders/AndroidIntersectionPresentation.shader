// Source-input approximation for the measured Cloud Intersection Remap family.
// Original D3D programs are unavailable here; depth/rim composition is authored.
Shader "Porting Lab/Android Intersection Presentation" {
 Properties {
  _MainTex("Recovered mask",2D)="white"{} _Cloud1Tex("Recovered cloud 1",2D)="white"{} _Cloud2Tex("Recovered cloud 2",2D)="white"{} _RemapTex("Recovered ramp",2D)="white"{}
  _TintColor("Recovered tint",Color)=(1,1,1,1) _CutoffScroll("Recovered scroll",Vector)=(0,0,0,0)
  _SrcBlend("Source blend",Float)=1 _DstBlend("Destination blend",Float)=1 _Cull("Source culling",Float)=0 _ZTest("Depth test",Float)=4
  _InvFade("Source soft factor",Float)=1 _SoftPower("Source soft power",Float)=1 _Boost("Source color boost",Float)=1 _AlphaBoost("Source alpha boost",Float)=1
  _RimPower("Source rim power",Float)=1 _RimStrength("Source rim strength",Float)=1 _IntersectionStrength("Source intersection strength",Float)=1 _ExternalAlpha("Source external alpha",Float)=1
  _FadeFromVertexColorsOn("Source vertex fade",Float)=0 _TriplanarOn("Source triplanar switch",Float)=0
  _AndroidRemapEnabled("Ramp present",Float)=0 _AndroidCloud1Enabled("Cloud 1 present",Float)=0 _AndroidCloud2Enabled("Cloud 2 present",Float)=0
 }
 SubShader {Tags{"Queue"="Transparent" "RenderType"="Transparent"}Blend [_SrcBlend] [_DstBlend] Cull [_Cull] ZTest [_ZTest] ZWrite Off
  Pass {CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fog
   #include "UnityCG.cginc"
   UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
   sampler2D _MainTex,_Cloud1Tex,_Cloud2Tex,_RemapTex;float4 _MainTex_ST,_Cloud1Tex_ST,_Cloud2Tex_ST,_TintColor,_CutoffScroll;
   float _InvFade,_SoftPower,_Boost,_AlphaBoost,_RimPower,_RimStrength,_IntersectionStrength,_ExternalAlpha,_FadeFromVertexColorsOn,_TriplanarOn,_AndroidRemapEnabled,_AndroidCloud1Enabled,_AndroidCloud2Enabled,_SrcBlend;
   struct appdata {float4 vertex:POSITION;float3 normal:NORMAL;float2 uv:TEXCOORD0;fixed4 color:COLOR;};
   struct v2f {float4 pos:SV_POSITION;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 normal:TEXCOORD2;float4 screen:TEXCOORD3;float eye:TEXCOORD4;fixed4 color:COLOR;UNITY_FOG_COORDS(5)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.screen=ComputeScreenPos(o.pos);o.eye=-UnityObjectToViewPos(v.vertex).z;o.color=v.color;UNITY_TRANSFER_FOG(o,o.pos);return o;}
   float cloudSample(sampler2D tex,float4 st,float2 scroll,v2f i){
    float2 offset=st.zw+_Time.y*scroll;
    if(_TriplanarOn<.5)return tex2D(tex,i.uv*st.xy+offset).r;
    float3 weight=abs(normalize(i.normal));weight/=max(.0001,weight.x+weight.y+weight.z);
    return dot(float3(tex2D(tex,i.world.yz*st.xy+offset).r,tex2D(tex,i.world.xz*st.xy+offset).r,tex2D(tex,i.world.xy*st.xy+offset).r),weight);
   }
   fixed4 frag(v2f i):SV_Target {
    float depth=LinearEyeDepth(SAMPLE_DEPTH_TEXTURE_PROJ(_CameraDepthTexture,UNITY_PROJ_COORD(i.screen)));
    float contact=pow(saturate(1-max(0,depth-i.eye)*max(0,_InvFade)),max(.001,_SoftPower));
    float rim=pow(1-saturate(abs(dot(normalize(i.normal),normalize(_WorldSpaceCameraPos-i.world)))),max(.001,_RimPower));
    float cloud=1;if(_AndroidCloud1Enabled>.5)cloud*=cloudSample(_Cloud1Tex,_Cloud1Tex_ST,_CutoffScroll.xy,i);if(_AndroidCloud2Enabled>.5)cloud*=cloudSample(_Cloud2Tex,_Cloud2Tex_ST,_CutoffScroll.zw,i);
    fixed4 mask=tex2D(_MainTex,i.uv*_MainTex_ST.xy+_MainTex_ST.zw);
    float intensity=saturate((contact*_IntersectionStrength+rim*_RimStrength)*cloud*mask.r);
    fixed4 color=lerp(mask,tex2D(_RemapTex,float2(intensity,.5)),_AndroidRemapEnabled)*_TintColor;
    float vertexFade=lerp(1,dot(i.color.rgb,float3(.2126,.7152,.0722))*i.color.a,saturate(_FadeFromVertexColorsOn));
    color.a=saturate(intensity*mask.a*_AlphaBoost)*saturate(_ExternalAlpha)*vertexFade*_TintColor.a;color.rgb*=_Boost;
    if(abs(_SrcBlend-1)<.1)color.rgb*=color.a;
    UNITY_APPLY_FOG_COLOR(i.fogCoord,color,fixed4(0,0,0,0));return color;
   }
  ENDCG}
 }
}
