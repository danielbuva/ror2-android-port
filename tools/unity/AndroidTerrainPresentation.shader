Shader "Porting Lab/Android Terrain Presentation" {
 Properties{
  _RedChannelTopTex("Recovered red top",2D)="white"{} _RedChannelSideTex("Recovered red side",2D)="white"{} _GreenChannelTex("Recovered green",2D)="white"{} _BlueChannelTex("Recovered blue",2D)="white"{}
  [Normal]_NormalTex("Recovered terrain normal",2D)="bump"{} _NormalStrength("Normal strength",Float)=0 _AndroidNormalEnabled("Normals present",Float)=0
  _Color("Tint",Color)=(1,1,1,1) _ColorsOn("Vertex channels",Float)=1 _RedChannelBias("Red bias",Float)=0 _GreenChannelBias("Green bias",Float)=0 _BlueChannelBias("Blue bias",Float)=0 _TextureFactor("Projection scale",Float)=.12
 }
 SubShader{Tags{"RenderType"="Opaque"}
  Pass{Tags{"LightMode"="ForwardBase"}CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fog
   #include "UnityCG.cginc"
   #include "Lighting.cginc"
   sampler2D _RedChannelTopTex,_RedChannelSideTex,_GreenChannelTex,_BlueChannelTex,_NormalTex;
   float4 _RedChannelTopTex_ST,_RedChannelSideTex_ST,_GreenChannelTex_ST,_BlueChannelTex_ST,_NormalTex_ST,_Color;
   float _ColorsOn,_RedChannelBias,_GreenChannelBias,_BlueChannelBias,_TextureFactor,_NormalStrength,_AndroidNormalEnabled;
   struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;float4 color:COLOR;};struct v2f{float4 pos:SV_POSITION;float3 world:TEXCOORD0;float3 normal:TEXCOORD1;float3 channels:TEXCOORD2;UNITY_FOG_COORDS(3)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.channels=lerp(float3(1,1,1),v.color.rgb,saturate(_ColorsOn));UNITY_TRANSFER_FOG(o,o.pos);return o;}
   fixed3 project(sampler2D tex,float4 st,float3 p,float3 w){return tex2D(tex,p.zy*st.xy+st.zw).rgb*w.x+tex2D(tex,p.xz*st.xy+st.zw).rgb*w.y+tex2D(tex,p.xy*st.xy+st.zw).rgb*w.z;}
   fixed4 frag(v2f i):SV_Target{
    float3 n=normalize(i.normal),w=pow(abs(n),4);w/=max(dot(w,float3(1,1,1)),.0001);float3 p=i.world*max(_TextureFactor,.001);
    fixed3 red=tex2D(_RedChannelSideTex,p.zy*_RedChannelSideTex_ST.xy+_RedChannelSideTex_ST.zw).rgb*w.x+tex2D(_RedChannelTopTex,p.xz*_RedChannelTopTex_ST.xy+_RedChannelTopTex_ST.zw).rgb*w.y+tex2D(_RedChannelSideTex,p.xy*_RedChannelSideTex_ST.xy+_RedChannelSideTex_ST.zw).rgb*w.z;
    fixed3 green=project(_GreenChannelTex,_GreenChannelTex_ST,p,w),blue=project(_BlueChannelTex,_BlueChannelTex_ST,p,w);
    float3 channels=max(i.channels,0)*exp2(clamp(float3(_RedChannelBias,_GreenChannelBias,_BlueChannelBias),-4,4)*4);if(dot(channels,float3(1,1,1))<.0001)channels=float3(1,1,1);channels/=dot(channels,float3(1,1,1));
    if(_AndroidNormalEnabled>.5){float3 a=UnpackNormal(tex2D(_NormalTex,p.zy*_NormalTex_ST.xy+_NormalTex_ST.zw)),b=UnpackNormal(tex2D(_NormalTex,p.xz*_NormalTex_ST.xy+_NormalTex_ST.zw)),c=UnpackNormal(tex2D(_NormalTex,p.xy*_NormalTex_ST.xy+_NormalTex_ST.zw));float3 detail=float3(a.z*sign(n.x),a.y,a.x)*w.x+float3(b.x,b.z*sign(n.y),b.y)*w.y+float3(c.x,c.y,c.z*sign(n.z))*w.z;n=normalize(lerp(n,detail,saturate(_NormalStrength)));}
    float3 albedo=(red*channels.r+green*channels.g+blue*channels.b)*_Color.rgb;fixed4 color=fixed4(albedo*(max(ShadeSH9(float4(n,1)),float3(.18,.18,.18))+_LightColor0.rgb*saturate(dot(n,normalize(_WorldSpaceLightPos0.xyz)))),1);UNITY_APPLY_FOG(i.fogCoord,color);return color;
   }
  ENDCG}
 }
}
