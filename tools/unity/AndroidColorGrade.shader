Shader "Porting Lab/Android Color Grade" {
 Properties{_MainTex("Camera image",2D)="white"{}}
 SubShader{Cull Off ZWrite Off ZTest Always
  Pass{CGPROGRAM
   #pragma vertex vert_img
   #pragma fragment frag
   #include "UnityCG.cginc"
   sampler2D _MainTex;
   // Identity until source scene grading is measured against the PC build.
   fixed4 frag(v2f_img i):SV_Target{return tex2D(_MainTex,i.uv);}
  ENDCG}
 }
}
