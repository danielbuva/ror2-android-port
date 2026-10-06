#ifndef PORTING_LAB_RECOVERED_REFLECTIONS
#define PORTING_LAB_RECOVERED_REFLECTIONS
#include "UnityGlobalIllumination.cginc"

// Native Unity probe selection/decoding/roughness, not RoR2's deferred lighting ramp.
half3 RecoveredReflection(float3 world,half3 normal,half3 view,half smoothness,half strength){
 if(strength<=0)return half3(0,0,0);
 UnityGIInput input=(UnityGIInput)0;
 input.worldPos=world;input.worldViewDir=view;
 input.probeHDR[0]=unity_SpecCube0_HDR;input.probeHDR[1]=unity_SpecCube1_HDR;
 #if defined(UNITY_SPECCUBE_BLENDING) || defined(UNITY_SPECCUBE_BOX_PROJECTION) || defined(UNITY_ENABLE_REFLECTION_BUFFERS)
 input.boxMin[0]=unity_SpecCube0_BoxMin;input.boxMin[1]=unity_SpecCube1_BoxMin;
 #endif
 #ifdef UNITY_SPECCUBE_BOX_PROJECTION
 input.boxMax[0]=unity_SpecCube0_BoxMax;input.boxMax[1]=unity_SpecCube1_BoxMax;
 input.probePosition[0]=unity_SpecCube0_ProbePosition;input.probePosition[1]=unity_SpecCube1_ProbePosition;
 #endif
 Unity_GlossyEnvironmentData glossy=UnityGlossyEnvironmentSetup(saturate(smoothness),view,normal,half3(0,0,0));
 return UnityGI_IndirectSpecular(input,1,glossy)*strength;
}

// Source strength/exponent; temporary Blinn response, without invented smoothness scaling.
half RecoveredDirectSpecular(half3 normal,half3 light,half3 view,half exponent,half strength){
 return strength>0?pow(saturate(dot(normal,normalize(light+view))),max(exponent,1))*strength:0;
}
#endif
