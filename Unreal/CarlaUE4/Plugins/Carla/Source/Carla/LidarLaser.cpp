// Fill out your copyright notice in the Description page of Project Settings.

#include "Carla.h"
#include "LidarLaser.h"
#include "Lidar.h"
#include "Runtime/Engine/Classes/Kismet/KismetMathLibrary.h"
#include "DrawDebugHelpers.h"
#include "Tagger.h"

int LidarLaser::GetId()
{
  return Id;
}

static std::vector<uint> LABEL_COLOR_MAP[] = {
    {  0u,   0u,   0u}, // None         =   0u,
    { 70u,  70u,  70u}, // Buildings    =   1u,
    {190u, 153u, 153u}, // Fences       =   2u,
    {250u, 170u, 160u}, // Other        =   3u,
    {220u,  20u,  60u}, // Pedestrians  =   4u,
    {153u, 153u, 153u}, // Poles        =   5u,
    {153u, 153u, 153u}, // RoadLines    =   6u,
    {128u,  64u, 128u}, // Roads        =   7u,
    {244u,  35u, 232u}, // Sidewalks    =   8u,
    {107u, 142u,  35u}, // Vegetation   =   9u,
    {  0u,   0u, 142u}, // Vehicles     =  10u,
    {102u, 102u, 156u}, // Walls        =  11u,
    {220u, 220u,   0u}  // TrafficSigns =  12u,
};

bool LidarLaser::Measure(
  ALidar* Lidar,
  float HorizontalAngle,
  FVector& XYZ,
  ECityObjectLabel& Label,
  bool Debug)
{
  FCollisionQueryParams TraceParams = FCollisionQueryParams(FName(TEXT("Laser_Trace")), true, Lidar);
  TraceParams.bTraceComplex = true;
  TraceParams.bReturnPhysicalMaterial = false;
  TraceParams.bFindInitialOverlaps = true;

  FHitResult HitInfo(ForceInit);

  FVector LidarBodyLoc = Lidar->GetActorLocation();
  FRotator LidarBodyRot = Lidar->GetActorRotation();
  FRotator LaserRot (VerticalAngle, HorizontalAngle, 0);  // float InPitch, float InYaw, float InRoll
  FRotator ResultRot = UKismetMathLibrary::ComposeRotators(
    LaserRot,
    LidarBodyRot
  );
  FVector EndTrace = Lidar->Range * UKismetMathLibrary::GetForwardVector(ResultRot) + LidarBodyLoc;

  Lidar->GetWorld()->LineTraceSingleByChannel(
    HitInfo,
    LidarBodyLoc,
    EndTrace,
    ECC_Visibility,
    TraceParams,
    FCollisionResponseParams::DefaultResponseParam
  );

  if (HitInfo.bBlockingHit)
  {
    Label = ATagger::GetTagOfTaggedComponent(*HitInfo.Component);

    if (Debug)
    {
      auto& color = LABEL_COLOR_MAP[int(Label)];
      DrawDebugPoint(
        Lidar->GetWorld(),
        HitInfo.ImpactPoint,
        10,  //size
        FColor(color[0], color[1], color[2]),
        false,  //persistent (never goes away)
        0.1  //point leaves a trail on moving object
      );
    }

    XYZ = LidarBodyLoc - HitInfo.ImpactPoint;
    XYZ = UKismetMathLibrary::RotateAngleAxis(
      XYZ,
      - LidarBodyRot.Yaw + 90,
      FVector(0, 0, 1)
    );

    return true;
  } else {
    XYZ = FVector(0, 0, 0);
    Label = ECityObjectLabel::None;
    return false;
  }
}
