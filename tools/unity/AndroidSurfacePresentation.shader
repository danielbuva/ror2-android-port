Shader "Porting Lab/Android Surface Presentation" {
 Properties {
  _MainTex("Recovered albedo",2D)="white"{} _Color("Recovered tint",Color)=(1,1,1,1) _TintColor("Indicator tint",Color)=(1,1,1,1)
  [Normal]_NormalTex("Recovered normals",2D)="bump"{} _NormalStrength("Normal strength",Float)=1 _AndroidNormalEnabled("Normals present",Float)=0
  _EmTex("Recovered emission",2D)="black"{} _EmColor("Emission tint",Color)=(0,0,0,1) _EmPower("Emission power",Float)=0 _EmissionEnabled("Emission enabled",Float)=1
  _SpecularStrength("Recovered specular",Float)=0 _SpecularExponent("Recovered exponent",Float)=1 _Smoothness("Recovered smoothness",Range(0,1))=0
  _EnableCutout("Cutout enabled",Float)=0 _Cutoff("Cutout",Range(0,1))=.5 _Cull("Culling",Float)=2
  _SnowTex("Recovered snow",2D)="white"{} _SnowColor("Snow tint",Color)=(1,1,1,1) _SnowBias("Snow bias",Float)=0 _AndroidSnowEnabled("Snow family",Float)=0
  _SnowOn("Source snow enabled",Float)=1 _TriplanarOn("Source surface projection",Float)=0 _TriplanarTextureFactor("Source projection scale",Float)=1
  _Fade("Original fade",Range(0,1))=1
 }
 CGINCLUDE
   #include "UnityCG.cginc"
   #include "Lighting.cginc"
   #include "AutoLight.cginc"
   sampler2D _MainTex,_NormalTex,_EmTex,_SnowTex;float4 _MainTex_ST,_NormalTex_ST,_EmTex_ST,_SnowTex_ST,_Color,_TintColor,_EmColor,_SnowColor;
   float _NormalStrength,_AndroidNormalEnabled,_EmPower,_EmissionEnabled,_SpecularStrength,_SpecularExponent,_Smoothness,_EnableCutout,_Cutoff,_SnowBias,_AndroidSnowEnabled,_Fade,_SnowOn,_TriplanarOn,_TriplanarTextureFactor;
   struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;float4 tangent:TANGENT;float2 uv:TEXCOORD0;};
   struct v2f{float4 pos:SV_POSITION;float3 world:TEXCOORD0;float3 normal:TEXCOORD1;float3 tangent:TEXCOORD2;float3 bitangent:TEXCOORD3;float2 uv:TEXCOORD4;UNITY_FOG_COORDS(5) UNITY_LIGHTING_COORDS(6,7)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.tangent=UnityObjectToWorldDir(v.tangent.xyz);o.bitangent=cross(o.normal,o.tangent)*v.tangent.w*unity_WorldTransformParams.w;o.uv=v.uv;UNITY_TRANSFER_FOG(o,o.pos);UNITY_TRANSFER_LIGHTING(o,v.uv);return o;}
   fixed4 shade(v2f i,bool additional){
    fixed4 tex=tex2D(_MainTex,i.uv*_MainTex_ST.xy+_MainTex_ST.zw);
    if(_TriplanarOn>.5){float3 w=pow(abs(normalize(i.normal)),4);w/=max(dot(w,float3(1,1,1)),.0001);float3 p=i.world*max(.001,_TriplanarTextureFactor);tex=tex2D(_MainTex,p.zy*_MainTex_ST.xy+_MainTex_ST.zw)*w.x+tex2D(_MainTex,p.xz*_MainTex_ST.xy+_MainTex_ST.zw)*w.y+tex2D(_MainTex,p.xy*_MainTex_ST.xy+_MainTex_ST.zw)*w.z;}
    if(_EnableCutout>.5)clip(tex.a-_Cutoff);clip(_Fade-.001);
    float3 n=normalize(i.normal);if(_AndroidNormalEnabled>.5&&dot(i.tangent,i.tangent)>.1){float3 normal=UnpackNormal(tex2D(_NormalTex,i.uv*_NormalTex_ST.xy+_NormalTex_ST.zw));normal.xy*=clamp(_NormalStrength,0,4);n=normalize(normal.x*normalize(i.tangent)+normal.y*normalize(i.bitangent)+normal.z*n);}
    float3 albedo=tex.rgb*_Color.rgb*_TintColor.rgb;float snow=saturate((n.y+_SnowBias)*2-1)*_AndroidSnowEnabled*saturate(_SnowOn);
    albedo=lerp(albedo,tex2D(_SnowTex,i.world.xz*_SnowTex_ST.xy+_SnowTex_ST.zw).rgb*_SnowColor.rgb,snow);
    float3 light=normalize(UnityWorldSpaceLightDir(i.world)),view=normalize(_WorldSpaceCameraPos-i.world);float lambert=saturate(dot(n,light));
    UNITY_LIGHT_ATTENUATION(attenuation,i,i.world);
    float spec=pow(saturate(dot(n,normalize(light+view))),max(2,_SpecularExponent*(1+_Smoothness*32)))*min(_SpecularStrength,2);
    fixed4 color=fixed4(_LightColor0.rgb*(albedo*lambert+spec)*attenuation,1);
    if(additional){UNITY_APPLY_FOG_COLOR(i.fogCoord,color,fixed4(0,0,0,0));}
    else{color.rgb+=albedo*max(ShadeSH9(float4(n,1)),0)+tex2D(_EmTex,i.uv*_EmTex_ST.xy+_EmTex_ST.zw).rgb*_EmColor.rgb*_EmPower*_EmissionEnabled;UNITY_APPLY_FOG(i.fogCoord,color);}
    return color;
   }
   fixed4 frag(v2f i):SV_Target{return shade(i,false);}
   fixed4 fragAdd(v2f i):SV_Target{return shade(i,true);}
 ENDCG
 SubShader {Tags{"RenderType"="Opaque"} Cull [_Cull]
  Pass {Tags{"LightMode"="ForwardBase"} CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fwdbase
   #pragma multi_compile_fog
  ENDCG}
  Pass {Tags{"LightMode"="ForwardAdd"} Blend One One ZWrite Off CGPROGRAM
   #pragma vertex vert
   #pragma fragment fragAdd
   #pragma multi_compile_fwdadd_fullshadows
   #pragma multi_compile_fog
  ENDCG}
  Pass {Tags{"LightMode"="ShadowCaster"} CGPROGRAM
   #pragma vertex castVert
   #pragma fragment castFrag
   #pragma multi_compile_shadowcaster
   struct shadowData{V2F_SHADOW_CASTER;float2 uv:TEXCOORD1;};
   shadowData castVert(appdata_base v){shadowData o;o.uv=TRANSFORM_TEX(v.texcoord,_MainTex);TRANSFER_SHADOW_CASTER_NORMALOFFSET(o);return o;}
   float4 castFrag(shadowData i):SV_Target{if(_EnableCutout>.5)clip(tex2D(_MainTex,i.uv).a-_Cutoff);clip(_Fade-.001);SHADOW_CASTER_FRAGMENT(i)}
  ENDCG}
 }
}
