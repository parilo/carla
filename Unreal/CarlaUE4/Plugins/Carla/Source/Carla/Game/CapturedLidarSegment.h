// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "Tagger.h"
#include "CapturedLidarSegment.generated.h"

///
/// Lidar segment captured by tick
///
USTRUCT()
struct FCapturedLidarLaserSegment
{
  GENERATED_USTRUCT_BODY()

  UPROPERTY(VisibleAnywhere)
  TArray<FVector> Points;
  TArray<ECityObjectLabel> Labels;
};

USTRUCT()
struct FCapturedLidarSegment
{
  GENERATED_USTRUCT_BODY()

  UPROPERTY(VisibleAnywhere)
  float HorizontalAngle = 0;

  UPROPERTY(VisibleAnywhere)
  TArray<FCapturedLidarLaserSegment> LidarLasersSegments;
};
