// Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma
// de Barcelona (UAB), and the INTEL Visual Computing Lab.
//
// This work is licensed under the terms of the MIT license.
// For a copy, see <https://opensource.org/licenses/MIT>.

#include "Carla.h"
#include "CarlaGameInstance.h"

#include "CarlaGameController.h"
#include "MockGameController.h"
#include "Settings/CarlaSettings.h"

UCarlaGameInstance::UCarlaGameInstance() {
  CarlaSettings = CreateDefaultSubobject<UCarlaSettings>(TEXT("CarlaSettings"));
  check(CarlaSettings != nullptr);
  CarlaSettings->LoadSettings();
  CarlaSettings->LogSettings();

  AdditionalCarlaSettings = CreateDefaultSubobject<UCarlaSettings>(TEXT("AdditionalCarlaSettings"));
  check(AdditionalCarlaSettings != nullptr);
  AdditionalCarlaSettings->LoadSettings();
  AdditionalCarlaSettings->LogSettings();
}

UCarlaGameInstance::~UCarlaGameInstance() {}

void UCarlaGameInstance::InitializeGameControllerIfNotPresent(
    const FMockGameControllerSettings &MockControllerSettings)
{
  if (GameController == nullptr) {
    if (CarlaSettings->bUseNetworking) {
      GameController = MakeUnique<CarlaGameController>();
    } else {
      GameController = MakeUnique<MockGameController>(MockControllerSettings);
      UE_LOG(LogCarla, Log, TEXT("Using mock CARLA controller"));
    }
  }
}
