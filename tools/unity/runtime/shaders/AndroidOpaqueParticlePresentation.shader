Shader "Porting Lab/Android Opaque Particle Presentation" {
 Properties {
  _MainTex("Source base RGB / alpha",2D)="white"{} _TintColor("Source tint",Color)=(1,1,1,1)
  _Cloud1Tex("Source cloud1",2D)="white"{} _Cloud2Tex("Source cloud2",2D)="white"{} _RemapTex("Source ramp",2D)="white"{}
  _AndroidCloud1Enabled("Cloud1 present",Float)=0 _AndroidCloud2Enabled("Cloud2 present",Float)=0 _AndroidRemapEnabled("Ramp present",Float)=0
  [Normal]_NormalTex("Source normals",2D)="bump"{} _NormalStrength("Source normal strength",Float)=1 _AndroidNormalEnabled("Normals present",Float)=0
  _CutoffScroll("Source scroll",Vector)=(0,0,0,0) _AlphaBoost("Source alpha boost",Float)=1 _Cutoff("Source cutoff",Range(0,1))=.5 _ExternalAlpha("Source external alpha",Float)=1
  _EmissionColor("Source emission",Color)=(0,0,0,0) _EmissionFromAlbedo("Source albedo emission",Float)=0
  _VertexAlphaOn("Source luminance alpha",Float)=0 _SpecularStrength("Source specular",Float)=0 _SpecularExponent("Source exponent",Float)=1 _Cull("Source cull",Float)=0
 }
 CGINCLUDE
  #include "UnityCG.cginc"
  #include "Lighting.cginc"
  #include "AutoLight.cginc"
  #include "AndroidRecoveredReflections.cginc"
  sampler2D _MainTex,_Cloud1Tex,_Cloud2Tex,_RemapTex,_NormalTex;
  float4 _MainTex_ST,_Cloud1Tex_ST,_Cloud2Tex_ST,_NormalTex_ST,_TintColor,_EmissionColor,_CutoffScroll;
  float _AndroidCloud1Enabled,_AndroidCloud2Enabled,_AndroidRemapEnabled,_AndroidNormalEnabled,_NormalStrength,_AlphaBoost,_Cutoff,_ExternalAlpha,_VertexAlphaOn,_EmissionFromAlbedo,_SpecularStrength,_SpecularExponent;
  struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;float4 tangent:TANGENT;fixed4 color:COLOR;float2 uv:TEXCOORD0;};
  struct v2f{float4 pos:SV_POSITION;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 normal:TEXCOORD2;float3 tangent:TEXCOORD3;float3 bitangent:TEXCOORD4;fixed4 color:COLOR;UNITY_FOG_COORDS(5) UNITY_LIGHTING_COORDS(6,7)};
  v2f vert(appdata v){v2f o;UNITY_INITIALIZE_OUTPUT(v2f,o);o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.tangent=UnityObjectToWorldDir(v.tangent.xyz);o.bitangent=cross(o.normal,o.tangent)*v.tangent.w*unity_WorldTransformParams.w;o.color=v.color;UNITY_TRANSFER_FOG(o,o.pos);UNITY_TRANSFER_LIGHTING(o,v.uv);return o;}
  half4 cloudColor(float2 uv,fixed4 vertex){
   half4 base=tex2D(_MainTex,uv*_MainTex_ST.xy+_MainTex_ST.zw);float cloud=1;
   if(_AndroidCloud1Enabled>.5)cloud*=tex2D(_Cloud1Tex,uv*_Cloud1Tex_ST.xy+_Cloud1Tex_ST.zw+_Time.y*_CutoffScroll.xy).r;
   if(_AndroidCloud2Enabled>.5)cloud*=tex2D(_Cloud2Tex,uv*_Cloud2Tex_ST.xy+_Cloud2Tex_ST.zw+_Time.y*_CutoffScroll.zw).r;
   half3 rgb=lerp(base.rgb,tex2D(_RemapTex,float2(saturate(base.r*cloud),.5)).rgb,_AndroidRemapEnabled)*_TintColor.rgb*vertex.rgb;
   float alpha=base.a*cloud*_AlphaBoost*_ExternalAlpha*_TintColor.a;
   if(_VertexAlphaOn>.5)rgb*=vertex.a;else alpha*=vertex.a;
   clip(alpha-_Cutoff);return half4(rgb,alpha);
  }
  half4 frag(v2f i):SV_Target{
   half4 base=cloudColor(i.uv,i.color);float3 n=normalize(i.normal);
   if(_AndroidNormalEnabled>.5&&dot(i.tangent,i.tangent)>.1){float3 detail=UnpackNormal(tex2D(_NormalTex,i.uv*_NormalTex_ST.xy+_NormalTex_ST.zw));detail.xy*=_NormalStrength;n=normalize(detail.x*normalize(i.tangent)+detail.y*normalize(i.bitangent)+detail.z*n);}
   float3 light=normalize(UnityWorldSpaceLightDir(i.world)),view=normalize(_WorldSpaceCameraPos-i.world);UNITY_LIGHT_ATTENUATION(attenuation,i,i.world);
   half4 color=half4(base.rgb*(max(ShadeSH9(float4(n,1)),0)+_LightColor0.rgb*saturate(dot(n,light))*attenuation)+_LightColor0.rgb*RecoveredDirectSpecular(n,light,view,_SpecularExponent,_SpecularStrength)*attenuation+_EmissionColor.rgb+base.rgb*_EmissionFromAlbedo,1);
   UNITY_APPLY_FOG(i.fogCoord,color);return color;
  }
 ENDCG
 SubShader{Tags{"Queue"="AlphaTest" "RenderType"="TransparentCutout" "IgnoreProjector"="True"}Cull [_Cull] ZWrite On ZTest LEqual Blend One Zero
  // Native cutoff/depth contract; forward lighting/cloud response is approximate.
  Pass{Tags{"LightMode"="ForwardBase"}CGPROGRAM
   #pragma target 3.0
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fwdbase
   #pragma multi_compile_fog
  ENDCG}
  Pass{Tags{"LightMode"="ShadowCaster"}CGPROGRAM
   #pragma target 3.0
   #pragma vertex castVert
   #pragma fragment castFrag
   #pragma multi_compile_shadowcaster
   struct shadowData{V2F_SHADOW_CASTER;float2 uv:TEXCOORD1;fixed4 color:COLOR;};
   shadowData castVert(appdata v){shadowData o;UNITY_INITIALIZE_OUTPUT(shadowData,o);o.uv=v.uv;o.color=v.color;TRANSFER_SHADOW_CASTER_NORMALOFFSET(o);return o;}
   float4 castFrag(shadowData i):SV_Target{cloudColor(i.uv,i.color);SHADOW_CASTER_FRAGMENT(i)}
  ENDCG}
 }
}
