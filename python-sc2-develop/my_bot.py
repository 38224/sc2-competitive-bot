from concurrent.futures.thread import _worker
from turtle import towards
from sc2 import maps
from sc2.ids.unit_typeid import UnitTypeId
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty
from sc2.bot_ai import BotAI
from sc2.game_state import GameState
from sc2.game_data import GameData
from sc2.game_info import GameInfo
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from typing import FrozenSet, Set
from loguru import logger
import random  
import numpy as np  
from sc2.ids.ability_id import AbilityId  


firstTry = 0

class RushBarracks(BotAI):
    
    async def on_step(self, iteration: int):
        global firstTry
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        cc: Unit = ccs.first
        #await self.distribute_workers()
        await self.buildSCV()
        ###################################################################################################################
        depot_placement_positions: FrozenSet[Point2] = self.main_base_ramp.corner_depots
        if(len(depot_placement_positions) ==2 and firstTry == 0 and self.time_formatted == "00:13"):
            firstTry = 1
            target_depot_location: Point2 = next(iter(depot_placement_positions ))
            self.workers.gathering.closest_to(target_depot_location).move(target_depot_location)

        depot_placement_positions: FrozenSet[Point2] = self.main_base_ramp.corner_depots
        barracks_placement_position: Point2 = self.main_base_ramp.barracks_correct_placement
        depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})

        # Filter locations close to finished supply depots
        if depots:
            depot_placement_positions: Set[Point2] = { 
                d for d in depot_placement_positions if depots.closest_distance_to(d) > 1
            }

        # Build depots
        if self.can_afford(UnitTypeId.SUPPLYDEPOT) and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0:
            if len(depot_placement_positions) == 0:
                return
            if len(depot_placement_positions) == 1:
                workers: Units = self.workers.gathering
                target_depot_location: Point2 = depot_placement_positions.pop()
                worker: Unit = workers.closest_to(depots[0])
                worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)
                return
            target_depot_location: Point2 = depot_placement_positions.pop()
            workers: Units = self.workers
            if workers:  # if workers were found
                worker: Unit = workers.furthest_to(self.townhalls.first)
                worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)

        # Build barracks
        if depots.ready and self.can_afford(UnitTypeId.BARRACKS) and self.already_pending(UnitTypeId.BARRACKS) == 0:
            if self.structures(UnitTypeId.BARRACKS).amount + self.already_pending(UnitTypeId.BARRACKS) > 0:
                return
            workers = self.workers
            if workers and barracks_placement_position:  # if workers were found
                worker: Unit = workers.furthest_to(self.townhalls.first)
                worker.build(UnitTypeId.BARRACKS, barracks_placement_position)

###################################################################################################################
    async def on_building_construction_started(self, unit: Unit):
        logger.info(f"Construction of building {unit} started at {unit.position}.")

    async def on_building_construction_complete(self, unit: Unit):
        logger.info(f"Construction of building {unit} completed at {unit.position}.")
 

    async def buildSCV(self):
        cc = self.townhalls.ready.random
        if ( self.can_afford(UnitTypeId.SCV) and cc.is_idle and self.workers.amount < self.townhalls.amount * 22):
            cc.train(UnitTypeId.SCV)

    async def buildDepo(self,worker,depot_placement_positions):
        cc = self.townhalls.ready.random
        pos = cc.position.towards(self.enemy_start_locations[0],10)
        if ( self.supply_left < 3 and self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0 and self.can_afford(UnitTypeId.SUPPLYDEPOT)):
            worker.build(UnitTypeId.SUPPLYDEPOT, depot_placement_positions)
            #await self.build(UnitTypeId.SUPPLYDEPOT, near = pos)

    async def buildBarrack(self,worker,barracks_placement_position):
        cc = self.townhalls.ready.random
        pos = cc.position.towards(self.enemy_start_locations[0],10)
        if ( self.already_pending(UnitTypeId.BARRACKS) == 0 and self.can_afford(UnitTypeId.BARRACKS)):
            #await self.build(GameInfo.barracks_in_middle)
            worker.build(UnitTypeId.BARRACKS, barracks_placement_position)
            #await self.build(UnitTypeId.BARRACKS, near = pos)

_map = random.choice(
    [
        # Most maps have 2 upper points at the ramp (len(self.main_base_ramp.upper) == 2)
        "AutomatonLE",
        "BlueshiftLE",
        "CeruleanFallLE",
        "KairosJunctionLE",
        "ParaSiteLE",
        "PortAleksanderLE",
        "StasisLE",
        "ParaSiteLE",  # Has 5 upper points at the main ramp
        "AcolyteLE",  # Has 4 upper points at the ramp to the in-base natural and 2 upper points at the small ramp
        "HonorgroundsLE",  # Has 4 or 9 upper points at the large main base ramp
    ]
)
run_game(
    maps.get(_map),
    [Bot(Race.Terran, RushBarracks()), Computer(Race.Zerg, Difficulty.Hard)],
    realtime=True,
    # sc2_version="4.10.1",
)

#class WorkerRushBot(BotAI):
#    async def on_step(self, iteration: int):
#        if iteration == 0:
#            for worker in self.workers:
#                worker.attack(self.enemy_start_locations[0])

# name='VeryEasy'   name='Easy'  name='Medium'   name='MediumHard'  name='Hard' name='Harder'  name='VeryHard'   name='CheatVision'  name='CheatMoney'  name='CheatInsane'