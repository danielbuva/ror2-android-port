Shader "Porting Lab/Android Particle Presentation" {
 Properties{
  _MainTex("Recovered mask",2D)="white"{} _RemapTex("Recovered ramp",2D)="white"{} _Cloud1Tex("Recovered cloud1",2D)="white"{} _Cloud2Tex("Recovered cloud2",2D)="white"{}
  _TintColor("Recovered tint",Color)=(1,1,1,1) _SrcBlend("Source blend",Float)=5 _DstBlend("Destination blend",Float)=10 _Cull("Culling",Float)=0 _ZTest("Depth test",Float)=4
  _Boost("Color boost",Float)=1 _AlphaBoost("Alpha boost",Float)=1 _AlphaBias("Alpha bias",Float)=0 _ExternalAlpha("Original external alpha",Float)=1 _Fade("Original fade",Float)=1
  _VertexColorOn("Source vertex colors",Float)=1 _VertexAlphaOn("Source vertex alpha",Float)=1 _DisableRemapOn("Disable ramp",Float)=0
  _CloudsOn("Source clouds",Float)=0 _AndroidRemapEnabled("Ramp present",Float)=0 _AndroidCloud1Enabled("Cloud1 present",Float)=0 _AndroidCloud2Enabled("Cloud2 present",Float)=0
  _CutoffScroll("Recovered scroll",Vector)=(0,0,0,0)
  _FresnelOn("Source Fresnel",Float)=0 _FresnelPower("Source rim power",Float)=1
 }
 SubShader{Tags{"Queue"="Transparent" "RenderType"="Transparent"}Blend [_SrcBlend] [_DstBlend] Cull [_Cull] ZTest [_ZTest] ZWrite Off
  Pass{CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fog
   #include "UnityCG.cginc"
   sampler2D _MainTex,_RemapTex,_Cloud1Tex,_Cloud2Tex;float4 _MainTex_ST,_Cloud1Tex_ST,_Cloud2Tex_ST,_TintColor,_CutoffScroll;
   float _Boost,_AlphaBoost,_AlphaBias,_ExternalAlpha,_Fade,_VertexColorOn,_VertexAlphaOn,_DisableRemapOn,_CloudsOn,_AndroidRemapEnabled,_AndroidCloud1Enabled,_AndroidCloud2Enabled,_FresnelOn,_FresnelPower,_SrcBlend;
   struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;fixed4 color:COLOR;float2 uv:TEXCOORD0;};struct v2f{float4 pos:SV_POSITION;fixed4 color:COLOR;float2 uv:TEXCOORD0;float3 world:TEXCOORD1;float3 normal:TEXCOORD2;UNITY_FOG_COORDS(3)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.uv=v.uv;o.color=v.color;o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);UNITY_TRANSFER_FOG(o,o.pos);return o;}
   fixed4 frag(v2f i):SV_Target{
    fixed4 mask=tex2D(_MainTex,i.uv*_MainTex_ST.xy+_MainTex_ST.zw);float cloud=1;
    if(_CloudsOn>.5&&_AndroidCloud1Enabled>.5)cloud*=tex2D(_Cloud1Tex,i.uv*_Cloud1Tex_ST.xy+_Cloud1Tex_ST.zw+_Time.y*_CutoffScroll.xy).r;
    if(_CloudsOn>.5&&_AndroidCloud2Enabled>.5)cloud*=tex2D(_Cloud2Tex,i.uv*_Cloud2Tex_ST.xy+_Cloud2Tex_ST.zw+_Time.y*_CutoffScroll.zw).r;
    float intensity=saturate(mask.r*cloud);fixed4 ramp=lerp(mask,tex2D(_RemapTex,float2(intensity,.5)),_AndroidRemapEnabled*(1-saturate(_DisableRemapOn)));
    fixed4 color=ramp*_TintColor;color.rgb*=lerp(1,i.color.rgb,saturate(_VertexColorOn))*clamp(_Boost,0,16);
    color.a=saturate(mask.a*cloud*_AlphaBoost-_AlphaBias)*_TintColor.a*lerp(1,i.color.a,saturate(_VertexAlphaOn))*saturate(_ExternalAlpha*_Fade);
    if(_FresnelOn>.5)color.a*=pow(1-saturate(abs(dot(normalize(i.normal),normalize(_WorldSpaceCameraPos-i.world)))),max(.01,_FresnelPower));
    // Source One blending needs masked RGB; alpha alone cannot hide the quad.
    if(abs(_SrcBlend-1)<.1)color.rgb*=color.a;
    UNITY_APPLY_FOG_COLOR(i.fogCoord,color,fixed4(0,0,0,0));return color;
   }
  ENDCG}
 }
}
