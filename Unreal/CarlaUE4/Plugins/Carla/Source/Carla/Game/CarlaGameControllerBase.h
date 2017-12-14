// Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma
// de Barcelona (UAB), and the INTEL Visual Computing Lab.
//
// This work is licensed under the terms of the MIT license.
// For a copy, see <https://opensource.org/licenses/MIT>.

#pragma once

#include "Array.h"

class AController;
class APlayerStart;
// class UCarlaSettings;
class UCarlaGameInstance;

/// Base class for a CARLA game controller.
class CARLA_API CarlaGameControllerBase
{
public:

  virtual ~CarlaGameControllerBase() {}

  // virtual void Initialize(UCarlaSettings &CarlaSettings) = 0;
  virtual void Initialize(UCarlaGameInstance &CarlaGameInstance) = 0;

  virtual APlayerStart *ChoosePlayerStart(const TArray<APlayerStart *> &AvailableStartSpots) = 0;

  virtual void RegisterPlayer(AController &NewPlayer) = 0;

  virtual void BeginPlay() = 0;

  virtual void Tick(float DeltaSeconds) = 0;
};
