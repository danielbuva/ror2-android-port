// Authored Android visibility shader; not recovered Hopoo shader source.
Shader "Porting Lab/Moon Pillar Beam Preview" {
 Properties {
  _MainTex ("Recovered beam mask", 2D) = "white" {}
  _Color ("Recovered tint", Color) = (1,1,1,1)
  _Boost ("Recovered brightness", Float) = 1
  _AlphaBoost ("Recovered alpha gain", Float) = 1
  _AlphaBias ("Recovered alpha bias", Float) = 0
  _ExternalAlpha ("Recovered external alpha", Float) = 1
  _BeamWidth ("Android readability width", Float) = 4
 }
 SubShader {
  Tags { "Queue"="Transparent" "RenderType"="Transparent" }
  Cull Off ZWrite Off ZTest LEqual Blend One One
  Pass { CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _MainTex;float4 _MainTex_ST,_Color;
   float _Boost,_AlphaBoost,_AlphaBias,_ExternalAlpha,_BeamWidth;
   struct appdata {float4 vertex:POSITION;float4 color:COLOR;float2 uv:TEXCOORD0;};
   struct v2f {float4 vertex:SV_POSITION;float4 color:COLOR;float2 uv:TEXCOORD0;};
   v2f vert(appdata v){v2f o;v.vertex.x*=_BeamWidth;o.vertex=UnityObjectToClipPos(v.vertex);o.color=v.color*_Color;o.uv=TRANSFORM_TEX(v.uv,_MainTex);return o;}
   fixed4 frag(v2f i):SV_Target {
    fixed4 mask=tex2D(_MainTex,i.uv);
    float alpha=saturate(mask.a*_AlphaBoost+_AlphaBias)*i.color.a*_ExternalAlpha;
    return fixed4(mask.rgb*i.color.rgb*alpha*max(1,_Boost),0);
   }
  ENDCG }
 }
}
