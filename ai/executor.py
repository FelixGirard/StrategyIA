# Under MIT License, see LICENSE.txt
""" Module contenant les Executors """

from abc import abstractmethod, ABCMeta

from .Util.types import AICommand

from .STA.Strategy.StrategyBook import StrategyBook
from .STA.Tactic.TacticBook import TacticBook
from .STA.Tactic import tactic_constants
from .STA.Tactic.GoGetBall import GoGetBall
from .STA.Tactic.GoalKeeper import GoalKeeper
from .STA.Tactic.GoToPosition import GoToPosition
from .STA.Tactic.Stop import Stop
from .STA.Tactic.CoverZone import CoverZone

from RULEngine.Util.Pose import Pose
from RULEngine.Util.Position import Position
from RULEngine.Util.constant import *


__author__ = 'RoboCupULaval'

class Executor(object, metaclass=ABCMeta):
    """ Classe abstraite des executeurs. """

    def __init__(self, info_manager):
        self.info_manager = info_manager

    @abstractmethod
    def exec(self):
        """ Méthode qui sera appelé à chaque coup de boucle. """
        pass

class StrategyExecutor(Executor):
    """
        StrategyExecutor est une classe du **Behavior Tree** qui s'occupe de
        déterminer la stratégie à choisir selon l'état de jeu calculé et
        d'assigner les tactiques aux robots pour optimiser les ressources.
    """
    def __init__(self, info_manager):
        """ Constructeur de la classe.
            :param info_manager: Référence à la facade InfoManager pour pouvoir
            accéder aux informations du GameState.
        """
        Executor.__init__(self, info_manager)
        self.strategic_state = self.info_manager.get_strategic_state() #ref au module intelligent
        self.strategy = None

    def exec(self):
        """
            #1 Détermine la stratégie en cours
            #2 Assigne les tactiques aux robots
        """
        self._set_strategy()
        self._assign_tactics()

    def _set_strategy(self):
        """
            Récupère l'état stratégique en cours, le score SWOT et choisit la
            meilleure stratégie pour le contexte.
        """
        if not self.info_manager.debug_manager.human_control:
            self.strategy_book = StrategyBook(self.info_manager)
            self.strategy = self.strategy_book.get_optimal_strategy()(self.info_manager)
        else:
            self.strategy = self.strategy_book.get_strategy("HumanControl")

    def _assign_tactics(self):
        """
            Détermine à quel robot assigner les tactiques de la stratégie en
            cours.
        """
        human_control = self.info_manager.debug_manager.human_control
        if not human_control:
            tactic_sequence = self.strategy.get_next_tactics_sequence()
            for i in range(0, 6):
                tactic = tactic_sequence[i]
                tactic.player_id = i
                self.info_manager.set_player_tactic(i, tactic_sequence[i])
        else:
            pass


class TacticExecutor(Executor):
    """ Fait avancer chaque FSM d'une itération. """
    def __init__(self, info_manager):
        """ Constructeur.
            :param info_manager: Référence à la facade InfoManager pour pouvoir
            accéder aux informations du GameState.
        """
        Executor.__init__(self, info_manager)

    def exec(self):
        """ Obtient la Tactic de chaque robot et fait progresser la FSM. """
        for i in range(0, 6):
            self.info_manager.get_player_tactic(i).exec()

class PathfinderExecutor(Executor):
    """ Récupère les paths calculés pour les robots et les assignent. """

    def __init__(self, info_manager):
        Executor.__init__(self, info_manager)
        self.pathfinder = None

    def exec(self):
        """
            Appel le module de pathfinder enregistré pour modifier le mouvement
            des joueurs de notre équipe.
        """
        self.pathfinder = self.info_manager.acquire_module('Pathfinder')
        if self.pathfinder: # on desactive l'executor si aucun module ne fournit de pathfinding
            paths = self.pathfinder.get_paths()
            for i in range(0, 6):
                self.info_manager.set_player_next_action(paths[i])

class ModuleExecutor(Executor):
    """ Met à jour tous les modules intelligents enregistré. """
    def __init__(self, info_manager):
        Executor.__init__(self, info_manager)

    def exec(self):
        modules = self.info_manager.modules
        for key in modules:
            try:
                modules[key].update()
            except:
                pass

class DebugExecutor(Executor):
    """ S'occupe d'interpréter les commandes de debug """
    def __init__(self, info_manager):
        Executor.__init__(self, info_manager)
        self.debug_manager = self.info_manager.debug_manager

    def exec(self):
        if self.debug_manager.human_control:
            self._exec_when_human_control()
        else:
            pass

    def _exec_when_human_control(self):
        debug_commands = self.debug_manager.get_ui_commands()
        for cmd in debug_commands:
            self._parse_command(cmd)

    def _parse_command(self, cmd):
        if cmd.is_strategy_cmd():
            self.info_manager.strategy = cmd.data['strategy']
        elif cmd.is_tactic_cmd():
            pid = self._sanitize_pid(cmd.data['id'])
            tactic_name = cmd.data['tactic']
            tactic_ref = self._parse_tactic(tactic_name, pid, cmd.data)
            self.info_manager.set_player_tactic(pid, tactic_ref)
        else:
            pass

    def _parse_tactic(self, tactic_name, pid, data):
        # TODO: redéfinir le paquet pour set une tactique pour que les données supplémentaire
        # soit un tuple
        target = data['target']
        tactic_ref = None
        if tactic_name == "goto_position":
            tactic_ref = GoToPosition(self.info_manager, pid, Pose(Position(target[0], target[1]), 0))
        elif tactic_name == "goalkeeper":
            tactic_ref = GoalKeeper(self.info_manager, pid)
        elif tactic_name == "cover_zone":
            tactic_ref = CoverZone(self.info_manager, pid, FIELD_Y_TOP, FIELD_Y_TOP/2, FIELD_X_LEFT, FIELD_X_LEFT/2)
        elif tactic_name == "get_ball":
            tactic_ref = GoGetBall(self.info_manager, pid)
        elif tactic_name == "tStop":
            tactic_ref = Stop(self.info_manager, pid)
        else:
            tactic_ref = Stop(self.info_manager, pid)

        return tactic_ref

    def _sanitize_pid(self, pid):
        if pid >= 0 and pid < 6:
            return pid
        elif pid >= 6 and pid < 12:
            return pid - 6
        else:
            return 0
