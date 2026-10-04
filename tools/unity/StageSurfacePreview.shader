Shader "Porting Lab/Stage Surface Preview" {
 Properties {
  _MainTex ("Recovered surface", 2D) = "white" {}
  _Color ("Recovered tint", Color) = (1,1,1,1)
  _Cutoff ("Recovered cutout", Range(0,1)) = .5
  _Cull ("Recovered culling", Float) = 2
 }
 SubShader { Tags { "RenderType"="TransparentCutout" "Queue"="AlphaTest" } Cull [_Cull]
  Pass { CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _MainTex;float4 _MainTex_ST,_Color;float _Cutoff;
   struct appdata {float4 vertex:POSITION;float3 normal:NORMAL;float2 uv:TEXCOORD0;};
   struct v2f {float4 vertex:SV_POSITION;float3 normal:TEXCOORD0;float2 uv:TEXCOORD1;};
   v2f vert(appdata v){v2f o;o.vertex=UnityObjectToClipPos(v.vertex);o.normal=UnityObjectToWorldNormal(v.normal);o.uv=TRANSFORM_TEX(v.uv,_MainTex);return o;}
   fixed4 frag(v2f i):SV_Target {fixed4 albedo=tex2D(_MainTex,i.uv);clip(albedo.a-_Cutoff);return fixed4(albedo.rgb*_Color.rgb*(.35+.65*saturate(dot(normalize(i.normal),normalize(float3(.4,.8,.6))))),1);}
  ENDCG }
 }
}
