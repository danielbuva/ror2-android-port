Shader "Porting Lab/Commando Preview" {
 Properties { _MainTex ("Recovered albedo", 2D) = "white" {} }
 SubShader { Tags { "RenderType"="Opaque" }
  Pass {
   CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _MainTex; float4 _MainTex_ST;
   struct appdata { float4 vertex:POSITION; float3 normal:NORMAL; float2 uv:TEXCOORD0; };
   struct v2f { float4 vertex:SV_POSITION; float3 normal:TEXCOORD0; float2 uv:TEXCOORD1; };
   v2f vert(appdata v){v2f o;o.vertex=UnityObjectToClipPos(v.vertex);o.normal=UnityObjectToWorldNormal(v.normal);o.uv=TRANSFORM_TEX(v.uv,_MainTex);return o;}
   fixed4 frag(v2f i):SV_Target {fixed4 c=tex2D(_MainTex,i.uv);c.rgb*=.35+.65*saturate(dot(normalize(i.normal),normalize(float3(.4,.8,.6))));c.a=1;return c;}
   ENDCG
  }
 }
}
