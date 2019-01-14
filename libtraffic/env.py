import gym
from gym import spaces
import enum
import random
import numpy as np


class Actions(enum.Enum):
    noAction = 0
    accelerate = 1
    decelerate = 2
    goLeftAction = 3
    goRightAction = 4


# relative Y speed equals 1 pos item per speed unit per frame

class Car:
    Length = 4
    Cell = 10

    def __init__(self, speed, cell_x, cell_y):
        self.speed = speed
        self.safe_speed = speed
        self.cell_x = cell_x
        self.pos_y = cell_y * self.Cell

    @property
    def cell_y(self):
        return self.pos_y // self.Cell

    @property
    def cell(self):
        return self.cell_x, self.cell_y

    def overlaps(self, car, safety_dist=0):
        assert isinstance(car, Car)
        if self.cell_x != car.cell_x:
            return False
        # if other car is ahead of us significantly
        if self.cell_y - car.cell_y - self.Length > safety_dist:
            return False
        # if other car is behind us
        if car.cell_y - self.cell_y - self.Length > safety_dist:
            return False
        return True

    def shift_forward(self, rel_speed):
        assert isinstance(rel_speed, int)
        # we're negating rel speed, as our Y coordinate is decreasing with moving forward
        self.pos_y -= rel_speed

    def is_inside(self, y_cells):
        return 0 <= self.cell_y <= (y_cells-self.Length)


class TrafficState:
    """
    State of the game
    """
    # Amount of cells we keep in front of us
    Safety_front = 4

    def __init__(self, width_lanes=7, height_cells=70, cars=20, history=0, init_speed_my=80, init_speed_others=65):
        self.width_lanes = width_lanes
        self.height_cells = height_cells
        self.cars_count = cars
        self.history_count = history
        self.init_speed = init_speed_others
        self.my_car = Car(init_speed_my, (width_lanes-1)//2, 2*height_cells//3)
        self.cars = self._make_cars_initial(cars)
        self._update_safe_speed(self.my_car, self.cars)
        self.state = self._render_state(self.my_car, self.cars)
        self.history = []
        # populate history
        for _ in range(self.history_count):
            self.tick()

    def _make_cars_initial(self, count):
        assert isinstance(count, int)

        res = []
        others = [self.my_car]
        while len(res) < count:
            cell_x, cell_y = self._find_spot(self.width_lanes, self.height_cells, others)
            car = Car(self.init_speed, cell_x, cell_y)
            res.append(car)
            others.append(car)
        return res

    def _make_car_new(self):
        positions = []
        for y in [0, self.height_cells-Car.Length]:
            for x in range(self.width_lanes):
                positions.append((x, y))

        random.shuffle(positions)
        for x, y in positions:
            speed = self.init_speed + random.randrange(-20, 20)
            car = Car(speed, x, y)
            if any(map(lambda c: car.overlaps(c), self.cars)):
                continue
            return car
        return None

    @staticmethod
    def _find_spot(max_x, max_y, cars):
        while True:
            x = random.randrange(max_x)
            y = random.randrange(max_y - Car.Length)
            test_car = Car(0, x, y)
            if any(map(lambda c: test_car.overlaps(c), cars)):
                continue
            return x, y

    def _update_safe_speed(self, my_car, cars):
        """
        For each car including our own calculate safe speed, taking into account car in front of us
        """
        assert isinstance(my_car, Car)
        assert isinstance(cars, list)

        cars_places = {(c.cell_x, c.cell_y): c for c in cars}

        # calculate for every lane individually
        for x in range(self.width_lanes):
            prev_car_ends = None
            prev_car_speed = None
            for y in range(self.height_cells):
                if my_car.cell == (x, y):
                    car = my_car
                else:
                    car = cars_places.get((x, y))
                if car is None:
                    continue
                # no car ahead or distance is enougth to keep the speed, remember our pos
                if prev_car_ends is None or y - prev_car_ends > self.Safety_front:
                    pass
                elif y - prev_car_ends == self.Safety_front:
                    car.safe_speed = prev_car_speed
                else:
                    car.safe_speed = prev_car_speed // 2
                prev_car_ends = y + Car.Length
                prev_car_speed = car.safe_speed

    def _render_state(self, my_car, cars):
        """
        Returns grid of relative speeds
        :return:
        """
        assert isinstance(my_car, Car)
        assert isinstance(cars, list)

        res = np.zeros((self.width_lanes, self.height_cells), dtype=np.float32)
        for car in cars:
            dspeed = car.safe_speed - my_car.safe_speed
            res[car.cell_x, car.cell_y:(car.cell_y + Car.Length)] = dspeed
        return res

    def _move_cars(self, my_car, cars):
        assert isinstance(my_car, Car)
        assert isinstance(cars, list)

        for car in cars:
            dspeed = car.safe_speed - my_car.safe_speed
            car.shift_forward(dspeed)

    def tick(self, action=Actions.noAction):
        """
        Move time one frame forward
        """
        # apply action to my car
        # perform random actions on other cars

        # change car's positions
        self._move_cars(self.my_car, self.cars)

        # throw away cars which have driven away
        # add new cars instead of them

        # update safe speed
        self._update_safe_speed(self.my_car, self.cars)

        # housekeep the history
        if self.history_count:
            self.history.append(self.state)
            if len(self.history) > self.history_count:
                self.history.pop(0)

        # render new state
        self.state = self._render_state(self.my_car, self.cars)


class EnvDeepTraffic(gym.Env):
    def __init__(self, lanes_side=3, patches_ahead=20, patches_behind=10):
        self.action_space = spaces.Discrete(len(Actions))
        self.observation_space = spaces.Box()
