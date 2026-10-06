Shader "Porting Lab/Android Water Presentation" {
 Properties{_Color("Water tint",Color)=(.12,.3,.4,.75) [Normal]_NormalTex("Recovered waves",2D)="bump"{}}
 SubShader{Tags{"Queue"="Transparent" "RenderType"="Transparent"}Blend SrcAlpha OneMinusSrcAlpha ZWrite Off Cull Off
  Pass{CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fog
   #include "UnityCG.cginc"
   sampler2D _NormalTex;float4 _NormalTex_ST,_Color;
   struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;};struct v2f{float4 pos:SV_POSITION;float3 world:TEXCOORD0;float3 normal:TEXCOORD1;UNITY_FOG_COORDS(2)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);UNITY_TRANSFER_FOG(o,o.pos);return o;}
   fixed4 frag(v2f i):SV_Target{float3 wave=UnpackNormal(tex2D(_NormalTex,i.world.xz*_NormalTex_ST.xy*.03+float2(.015,.009)*_Time.y));float3 n=normalize(i.normal+float3(wave.x,0,wave.y)*.3);float fresnel=pow(1-saturate(dot(n,normalize(_WorldSpaceCameraPos-i.world))),3);fixed4 color=fixed4(lerp(_Color.rgb,float3(.5,.65,.75),fresnel),max(.35,_Color.a));UNITY_APPLY_FOG(i.fogCoord,color);return color;}
  ENDCG}
 }
}
