Shader "Porting Lab/Commando Material Preview" {
 Properties {
  _MainTex ("Recovered albedo", 2D) = "white" {}
  _Color ("Tint", Color) = (1,1,1,1)
  _EmTex ("Recovered emission", 2D) = "black" {}
  _EmColor ("Emission color", Color) = (0,0,0,1)
  _EmPower ("Emission power", Float) = 0
  _EmissionEnabled ("Diagnostic emission", Float) = 1
 }
 SubShader { Tags { "RenderType"="Opaque" }
  Pass { CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _MainTex,_EmTex; float4 _MainTex_ST,_Color,_EmColor; float _EmPower,_EmissionEnabled;
   struct appdata { float4 vertex:POSITION; float3 normal:NORMAL; float2 uv:TEXCOORD0; };
   struct v2f { float4 vertex:SV_POSITION; float3 normal:TEXCOORD0; float2 uv:TEXCOORD1; };
   v2f vert(appdata v){v2f o;o.vertex=UnityObjectToClipPos(v.vertex);o.normal=UnityObjectToWorldNormal(v.normal);o.uv=TRANSFORM_TEX(v.uv,_MainTex);return o;}
   fixed4 frag(v2f i):SV_Target {fixed3 albedo=tex2D(_MainTex,i.uv).rgb*_Color.rgb;fixed3 diffuse=albedo*(.35+.65*saturate(dot(normalize(i.normal),normalize(float3(.4,.8,.6)))));fixed3 glow=tex2D(_EmTex,i.uv).rgb*_EmColor.rgb*_EmPower*_EmissionEnabled;return fixed4(diffuse+glow,1);}
  ENDCG }
 }
}
