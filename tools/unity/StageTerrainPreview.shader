Shader "Porting Lab/Stage Terrain Preview" {
 Properties {
  _RedChannelTopTex ("Recovered red top", 2D) = "white" {}
  _RedChannelSideTex ("Recovered red side", 2D) = "white" {}
  _GreenChannelTex ("Recovered green", 2D) = "white" {}
  _BlueChannelTex ("Recovered blue", 2D) = "white" {}
  _Color ("Recovered tint", Color) = (1,1,1,1)
  _ColorsOn ("Use recovered vertex channels", Float) = 1
  _RedChannelBias ("Red bias", Float) = 1
  _GreenChannelBias ("Green bias", Float) = 1
  _BlueChannelBias ("Blue bias", Float) = 1
  _TextureFactor ("Projection scale", Float) = .12
 }
 SubShader { Tags { "RenderType"="Opaque" }
  Pass { CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _RedChannelTopTex,_RedChannelSideTex,_GreenChannelTex,_BlueChannelTex;
   float4 _RedChannelTopTex_ST,_RedChannelSideTex_ST,_GreenChannelTex_ST,_BlueChannelTex_ST,_Color;
   float _ColorsOn,_RedChannelBias,_GreenChannelBias,_BlueChannelBias,_TextureFactor;
   struct appdata {float4 vertex:POSITION;float3 normal:NORMAL;float4 color:COLOR;};
   struct v2f {float4 vertex:SV_POSITION;float3 world:TEXCOORD0;float3 normal:TEXCOORD1;float3 channels:TEXCOORD2;};
   v2f vert(appdata v){v2f o;o.vertex=UnityObjectToClipPos(v.vertex);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.channels=lerp(float3(1,1,1),v.color.rgb,saturate(_ColorsOn));return o;}
   fixed3 project(sampler2D tex,float4 st,float3 p,float3 weights){
    return tex2D(tex,p.zy*st.xy+st.zw).rgb*weights.x+tex2D(tex,p.xz*st.xy+st.zw).rgb*weights.y+tex2D(tex,p.xy*st.xy+st.zw).rgb*weights.z;
   }
   fixed4 frag(v2f i):SV_Target {
    float3 normal=normalize(i.normal),weights=pow(abs(normal),4);weights/=max(dot(weights,float3(1,1,1)),.0001);
    float3 p=i.world*max(_TextureFactor,.001);
    fixed3 red=tex2D(_RedChannelSideTex,p.zy*_RedChannelSideTex_ST.xy+_RedChannelSideTex_ST.zw).rgb*weights.x+tex2D(_RedChannelTopTex,p.xz*_RedChannelTopTex_ST.xy+_RedChannelTopTex_ST.zw).rgb*weights.y+tex2D(_RedChannelSideTex,p.xy*_RedChannelSideTex_ST.xy+_RedChannelSideTex_ST.zw).rgb*weights.z;
    fixed3 green=project(_GreenChannelTex,_GreenChannelTex_ST,p,weights),blue=project(_BlueChannelTex,_BlueChannelTex_ST,p,weights);
    float3 channels=max(i.channels,0)*max(float3(_RedChannelBias,_GreenChannelBias,_BlueChannelBias),.001);if(dot(channels,float3(1,1,1))<.0001)channels=float3(1,1,1);channels/=dot(channels,float3(1,1,1));
    return fixed4((red*channels.r+green*channels.g+blue*channels.b)*_Color.rgb*(.35+.65*saturate(dot(normal,normalize(float3(.4,.8,.6))))),1);
   }
  ENDCG }
 }
}
