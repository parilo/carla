// Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma
// de Barcelona (UAB), and the INTEL Visual Computing Lab.
//
// This work is licensed under the terms of the MIT license.
// For a copy, see <https://opensource.org/licenses/MIT>.

#include "Carla.h"
#include "CarlaGameController.h"

#include "CarlaVehicleController.h"

#include "Settings/CarlaSettings.h"
#include "CarlaGameInstance.h"
#include "CarlaServer.h"

using Errc = CarlaServer::ErrorCode;

static constexpr bool BLOCKING = true;
static constexpr bool NON_BLOCKING = false;

CarlaGameController::CarlaGameController() :
  Server(nullptr),
  Player(nullptr) {}

CarlaGameController::~CarlaGameController() {}

// void CarlaGameController::Initialize(UCarlaSettings &InCarlaSettings)
void CarlaGameController::Initialize(UCarlaGameInstance &CarlaGameInstance)
{
  // CarlaSettings = &InCarlaSettings;
  CarlaSettings = &CarlaGameInstance.GetCarlaSettings();

  // Initialize server if missing.
  if (Server == nullptr) {
    Server = MakeUnique<CarlaServer>(CarlaSettings->WorldPort, CarlaSettings->ServerTimeOut);
    if ((Errc::Success != Server->Connect()) ||
        (Errc::Success != Server->ReadNewEpisode(*CarlaSettings, BLOCKING))) {
      UE_LOG(LogCarlaServer, Warning, TEXT("Failed to initialize, server needs restart"));
      Server = nullptr;
    }
  }

  // Initialize additional servers
  AdditionalClientsServers.Empty();
  UCarlaSettings* AdditionalSettings = &CarlaGameInstance.GetAdditionalCarlaSettings();
  UE_LOG(LogCarlaServer, Warning, TEXT("--- num of additional players %d"), CarlaSettings->NumOfAdditionalPlayers);
  for (size_t i=0; i<CarlaSettings->NumOfAdditionalPlayers; i++)
  {
    AdditionalClientsServers.Add(MakeUnique<CarlaServer>(
      CarlaSettings->WorldPort + 3*(i+1),
      CarlaSettings->ServerTimeOut));
    auto& AdditionalServer = AdditionalClientsServers[i];
    if ((Errc::Success != AdditionalServer->Connect()) ||
        (Errc::Success != AdditionalServer->ReadNewEpisode(*AdditionalSettings, BLOCKING))) {
      UE_LOG(
        LogCarlaServer, Warning,
        TEXT("Failed to initialize additional client server, server needs restart"));
      AdditionalServer = nullptr;
    }
  }
}

APlayerStart *CarlaGameController::ChoosePlayerStart(
    const TArray<APlayerStart *> &AvailableStartSpots)
{
  check(AvailableStartSpots.Num() > 0);
  // Send scene description.
  if (Server != nullptr) {
    if (Errc::Success != Server->SendSceneDescription(AvailableStartSpots, BLOCKING)) {
      UE_LOG(LogCarlaServer, Warning, TEXT("Failed to send scene description, server needs restart"));
      Server = nullptr;
    }
  }

  // Read episode start.
  uint32 StartIndex = 0u; // default.
  if (Server != nullptr) {
    if (Errc::Success != Server->ReadEpisodeStart(StartIndex, BLOCKING)) {
      UE_LOG(LogCarlaServer, Warning, TEXT("Failed to read episode start, server needs restart"));
      Server = nullptr;
    }
  }

  for (size_t i=0; i<AdditionalClientsServers.Num(); i++)
  {
    auto& AdditionalServer = AdditionalClientsServers[i];
    // Send scene description.
    if (AdditionalServer != nullptr) {
      if (Errc::Success != AdditionalServer->SendSceneDescription(AvailableStartSpots, BLOCKING)) {
        UE_LOG(LogCarlaServer, Warning, TEXT("AdditionalServer: Failed to send scene description, server needs restart"));
        AdditionalServer = nullptr;
      }
    }

    // Read episode start.
    StartIndex = 0u; // default.
    if (AdditionalServer != nullptr) {
      if (Errc::Success != AdditionalServer->ReadEpisodeStart(StartIndex, BLOCKING)) {
        UE_LOG(LogCarlaServer, Warning, TEXT("AdditionalServer: Failed to read episode start, server needs restart"));
        AdditionalServer = nullptr;
      }
    }
  }

  if (static_cast<int64>(StartIndex) >= AvailableStartSpots.Num()) {
    UE_LOG(LogCarlaServer, Warning, TEXT("Client requested an invalid player start, using default one instead."));
    StartIndex = 0u;
  }

  return AvailableStartSpots[StartIndex];
}

void CarlaGameController::RegisterPlayer(AController &NewPlayer)
{
  Player = Cast<ACarlaVehicleController>(&NewPlayer);
  check(Player != nullptr);
}

void CarlaGameController::BeginPlay()
{
  check(Player != nullptr);
  GameState = Cast<ACarlaGameState>(Player->GetWorld()->GetGameState());
  check(GameState != nullptr);
  if (Server != nullptr) {
    if (Errc::Success != Server->SendEpisodeReady(BLOCKING)) {
      UE_LOG(LogCarlaServer, Warning, TEXT("Failed to read episode start, server needs restart"));
      Server = nullptr;
    }
  }

  for (size_t i=0; i<AdditionalClientsServers.Num(); i++)
  {
    auto& AdditionalServer = AdditionalClientsServers[i];
    if (AdditionalServer != nullptr) {
      if (Errc::Success != AdditionalServer->SendEpisodeReady(BLOCKING)) {
        UE_LOG(LogCarlaServer, Warning,
          TEXT("Additional Server: Failed to read episode start, server needs restart"));
        AdditionalServer = nullptr;
      }
    }
  }
}

void CarlaGameController::Tick(float DeltaSeconds)
{
  check(Player != nullptr);
  check(CarlaSettings != nullptr);

  if (Server == nullptr) {
    UE_LOG(LogCarlaServer, Warning, TEXT("Client disconnected, server needs restart"));
    RestartLevel();
    return;
  }

  // Check if the client requested a new episode.
  {
    auto ec = Server->ReadNewEpisode(*CarlaSettings, NON_BLOCKING);
    switch (ec) {
      case Errc::Success:
        RestartLevel();
        return;
      case Errc::Error:
        Server = nullptr;
        return;
      default:
        break; // fallthrough...
    }
  }

  // Send measurements.
  {
    check(GameState != nullptr);
    if (Errc::Error == Server->SendMeasurements(
            *GameState,
            Player->GetPlayerState(),
            CarlaSettings->bSendNonPlayerAgentsInfo)) {
      Server = nullptr;
      return;
    }
  }



  for (size_t i=0; i<AdditionalClientsServers.Num(); i++)
  {
    auto& AdditionalServer = AdditionalClientsServers[i];

    if (AdditionalServer == nullptr) {
      UE_LOG(LogCarlaServer, Warning, TEXT("--- additional server disconnected"));
      continue;
      // RestartLevel();
      // return;
    }

    // Check if the client requested a new episode.
    {
      auto ec = AdditionalServer->ReadNewEpisode(*CarlaSettings, NON_BLOCKING);
      switch (ec) {
        case Errc::Success:
          UE_LOG(LogCarlaServer, Warning, TEXT("--- additional server restart level received"));
          // RestartLevel();
          // return;
          continue;
        case Errc::Error:
          AdditionalServer = nullptr;
          return;
        default:
          break; // fallthrough...
      }
    }

    // Send measurements.
    {
      check(GameState != nullptr);
      if (Errc::Error == AdditionalServer->SendMeasurements(
              *GameState,
              Player->GetPlayerState(),
              CarlaSettings->bSendNonPlayerAgentsInfo)) {
        AdditionalServer = nullptr;
        UE_LOG(LogCarlaServer, Warning, TEXT("--- additional server send measurements fail"));
        continue;
      }
    }
  }



  // Read control, block if the settings say so.
  {
    const bool bShouldBlock = CarlaSettings->bSynchronousMode;
    if (Errc::Error == Server->ReadControl(*Player, bShouldBlock)) {
      Server = nullptr;
      return;
    }
  }



  for (size_t i=0; i<AdditionalClientsServers.Num(); i++)
  {
    auto& AdditionalServer = AdditionalClientsServers[i];

    if (AdditionalServer == nullptr) {
      UE_LOG(LogCarlaServer, Warning, TEXT("--- additional server disconnected"));
      continue;
      // RestartLevel();
      // return;
    }

    // Read control, block if the settings say so.
    {
      const bool bShouldBlock = CarlaSettings->bSynchronousMode;
      if (Errc::Error == AdditionalServer->ReadControl(*Player, bShouldBlock)) {
        AdditionalServer = nullptr;
        UE_LOG(LogCarlaServer, Warning, TEXT("--- additional server read control fail"));
        continue;
      }
    }
  }
}

void CarlaGameController::RestartLevel()
{
  UE_LOG(LogCarlaServer, Log, TEXT("Restarting the level..."));
  Player->RestartLevel();
}
