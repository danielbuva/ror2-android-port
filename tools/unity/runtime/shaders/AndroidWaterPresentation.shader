Shader "Porting Lab/Android Water Presentation" {
 Properties{
  _Color("Source surface tint",Color)=(1,1,1,1) _DepthColor("Source depth tint",Color)=(1,1,1,1) _CubeColor("Source reflection tint",Color)=(1,1,1,1)
  [Normal]_BumpMap("Source waves",2D)="bump"{} [Normal]_BumpMapLarge("Source large waves",2D)="bump"{} _Cube("Source reflection",Cube)="black"{}
  [Normal]_NormalTex("Existing lab binding",2D)="bump"{}
  _BumpStrength("Source waves strength",Float)=0 _BumpLargeStrength("Source large strength",Float)=0 _EnableLargeBump("Source large waves",Float)=0
  _Speeds("Source wave speeds",Vector)=(0,0,0,0) _SpeedsLarge("Source large speeds",Vector)=(0,0,0,0)
  _WorldSpace("Source projection",Float)=0 _Reflection("Source reflection strength",Float)=0 _RimPower("Source rim power",Float)=1 _EnableFog("Source fog toggle",Float)=1
 }
 SubShader{Tags{"Queue"="Transparent" "RenderType"="Transparent"}Blend SrcAlpha OneMinusSrcAlpha ZWrite Off Cull Off
  Pass{CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #pragma multi_compile_fog
   #include "UnityCG.cginc"
   sampler2D _BumpMap,_BumpMapLarge;samplerCUBE _Cube;
   float4 _BumpMap_ST,_BumpMapLarge_ST,_Color,_DepthColor,_CubeColor,_Speeds,_SpeedsLarge;
   float _BumpStrength,_BumpLargeStrength,_EnableLargeBump,_WorldSpace,_Reflection,_RimPower,_EnableFog;
   struct appdata{float4 vertex:POSITION;float3 normal:NORMAL;float4 tangent:TANGENT;float2 uv:TEXCOORD0;};
   struct v2f{float4 pos:SV_POSITION;float3 world:TEXCOORD0;float3 normal:TEXCOORD1;float3 tangent:TEXCOORD2;float3 bitangent:TEXCOORD3;float2 uv:TEXCOORD4;UNITY_FOG_COORDS(5)};
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.world=mul(unity_ObjectToWorld,v.vertex).xyz;o.normal=UnityObjectToWorldNormal(v.normal);o.tangent=UnityObjectToWorldDir(v.tangent.xyz);o.bitangent=cross(o.normal,o.tangent)*v.tangent.w*unity_WorldTransformParams.w;o.uv=v.uv;UNITY_TRANSFER_FOG(o,o.pos);return o;}
   fixed4 frag(v2f i):SV_Target{
    // Source inputs retained; two-layer normal/reflection response remains approximate.
    float2 uv=lerp(i.uv,i.world.xz,saturate(_WorldSpace));
    float3 a=UnpackNormal(tex2D(_BumpMap,uv*_BumpMap_ST.xy+_BumpMap_ST.zw+_Time.y*_Speeds.xy));
    float3 b=UnpackNormal(tex2D(_BumpMap,uv*_BumpMap_ST.xy+_BumpMap_ST.zw+_Time.y*_Speeds.zw));
    float2 waves=(a.xy+b.xy)*_BumpStrength;
    if(_EnableLargeBump>.5){float3 large=UnpackNormal(tex2D(_BumpMapLarge,uv*_BumpMapLarge_ST.xy+_BumpMapLarge_ST.zw+_Time.y*_SpeedsLarge.xy));waves+=large.xy*_BumpLargeStrength;}
    float3 n=normalize(i.normal);if(dot(i.tangent,i.tangent)>.1)n=normalize(waves.x*normalize(i.tangent)+waves.y*normalize(i.bitangent)+n);else n=normalize(n+float3(waves.x,0,waves.y));
    float3 view=normalize(_WorldSpaceCameraPos-i.world);float rim=pow(1-saturate(abs(dot(n,view))),max(.01,_RimPower));
    float3 reflection=texCUBE(_Cube,reflect(-view,n)).rgb*_CubeColor.rgb;
    fixed4 color=fixed4(lerp(_Color.rgb*_DepthColor.rgb,reflection,saturate(_Reflection)*rim),_Color.a);
    if(_EnableFog>.5){UNITY_APPLY_FOG(i.fogCoord,color);}return color;
   }
  ENDCG}
 }
}
