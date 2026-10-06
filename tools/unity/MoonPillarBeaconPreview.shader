// Authored wayfinding fallback. Source pillar FX activation owns visibility.
Shader "Porting Lab/Moon Pillar Beacon Preview" {
 SubShader {
  Tags { "Queue"="Transparent" "RenderType"="Transparent" }
  Cull Off ZWrite Off ZTest LEqual Blend SrcAlpha One
  Pass { CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   struct appdata {float4 vertex:POSITION;float4 color:COLOR;float2 uv:TEXCOORD0;};
   struct v2f {float4 vertex:SV_POSITION;float4 color:COLOR;float2 uv:TEXCOORD0;};
   v2f vert(appdata v){v2f o;o.vertex=UnityObjectToClipPos(v.vertex);o.color=v.color;o.uv=v.uv;return o;}
   fixed4 frag(v2f i):SV_Target {
    float edge=saturate(1-abs(i.uv.y*2-1));
    return fixed4(i.color.rgb*2,i.color.a*edge*edge);
   }
  ENDCG }
 }
}
