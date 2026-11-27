Shader "Hidden/Lab/TextureMipFixture"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        _Cube ("Cubemap", Cube) = "" {}
    }
    SubShader
    {
        Cull Off ZWrite Off ZTest Always
        CGINCLUDE
        #include "UnityCG.cginc"
        sampler2D _MainTex;
        samplerCUBE _Cube;
        float _Mip;
        int _Face;

        float4 Sample2D(v2f_img input) : SV_Target
        {
            return tex2Dlod(_MainTex, float4(input.uv, 0, _Mip));
        }

        float4 SampleCube(v2f_img input) : SV_Target
        {
            float2 uv = input.uv * 2 - 1;
            float3 direction;
            if (_Face == 0) direction = float3(1, -uv.y, -uv.x);
            else if (_Face == 1) direction = float3(-1, -uv.y, uv.x);
            else if (_Face == 2) direction = float3(uv.x, 1, uv.y);
            else if (_Face == 3) direction = float3(uv.x, -1, -uv.y);
            else if (_Face == 4) direction = float3(uv.x, -uv.y, 1);
            else direction = float3(-uv.x, -uv.y, -1);
            return texCUBElod(_Cube, float4(direction, _Mip));
        }
        ENDCG

        Pass
        {
            CGPROGRAM
            #pragma target 3.0
            #pragma vertex vert_img
            #pragma fragment Sample2D
            ENDCG
        }
        Pass
        {
            CGPROGRAM
            #pragma target 3.0
            #pragma vertex vert_img
            #pragma fragment SampleCube
            ENDCG
        }
    }
}
