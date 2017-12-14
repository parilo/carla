// Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma
// de Barcelona (UAB), and the INTEL Visual Computing Lab.
//
// This work is licensed under the terms of the MIT license.
// For a copy, see <https://opensource.org/licenses/MIT>.

#pragma once

#include "CarlaGameControllerBase.h"

class ACarlaGameState;
class ACarlaVehicleController;
class CarlaServer;
class UCarlaSettings;

/// Implements remote control of game and player.
class CARLA_API CarlaGameController : public CarlaGameControllerBase
{
public:

  explicit CarlaGameController();

  ~CarlaGameController();

  // virtual void Initialize(UCarlaSettings &CarlaSettings) override;
  virtual void Initialize(UCarlaGameInstance &CarlaGameInstance) override;

  virtual APlayerStart *ChoosePlayerStart(const TArray<APlayerStart *> &AvailableStartSpots) override;

  virtual void RegisterPlayer(AController &NewPlayer) override;

  virtual void BeginPlay() override;

  virtual void Tick(float DeltaSeconds) override;

private:

  void RestartLevel();

  TUniquePtr<CarlaServer> Server;
  TArray<TUniquePtr<CarlaServer>> AdditionalClientsServers;

  ACarlaVehicleController *Player = nullptr;

  const ACarlaGameState *GameState = nullptr;

  UCarlaSettings *CarlaSettings = nullptr;
};
