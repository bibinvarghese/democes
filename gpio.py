
import sys
import time

class UI(object):
  """Abstract UI class. Subclassed by specific board implementations."""
  def __init__(self):
    self._button_state = [False for _ in self._buttons]
    current_time = time.time()
    self._button_state_last_change = [current_time for _ in self._buttons]
    self._debounce_interval = 0.1 # seconds

  def setOnlyLED(self, index):
    for i in range(len(self._LEDs)): self.setLED(i, False)
    if index is not None: self.setLED(index, True)

  def isButtonPressed(self, index):
    buttons = self.getButtonState()
    return buttons[index]

  def setLED(self, index, state):
    raise NotImplementedError()

  def getButtonState(self):
    raise NotImplementedError()

  def getDebouncedButtonState(self):
    t = time.time()
    for i,new in enumerate(self.getButtonState()):
      if not new:
        self._button_state[i] = False
        continue
      old = self._button_state[i]
      if ((t-self._button_state_last_change[i]) >
             self._debounce_interval) and not old:
        self._button_state[i] = True
      else:
        self._button_state[i] = False
      self._button_state_last_change[i] = t
    return self._button_state

  def testButtons(self, times):
    for t in range(0,times):
      for i in range(5):
        self.setLED(i, self.isButtonPressed(i))
      print("Buttons: ", " ".join([str(i) for i,v in
          enumerate(self.getButtonState()) if v]))
      time.sleep(0.01)

  def wiggleLEDs(self, reps=3):
    for i in range(reps):
      for i in range(5):
        self.setLED(i, True)
        time.sleep(0.05)
        self.setLED(i, False)


class UI_EdgeTpuDevBoard(UI):
  def __init__(self):
    global GPIO, PWM
    from periphery import GPIO, PWM, GPIOError
    def initPWM(pin):
      pwm = PWM(pin, 0)
      pwm.frequency = 1e3
      pwm.duty_cycle = 0
      pwm.enable()
      return pwm
    try:
      self._buttons = [
                       GPIO(6, "in"),
                       GPIO(138, "in"),
                       GPIO(140,"in"),
                       GPIO(7, "in"),
                       GPIO(141, "in"),
                      ]
      self._LEDs = [
                    initPWM(2),
                    GPIO(73, "out"),
                    initPWM(1),
                    initPWM(0),
                    GPIO(77 , "out"),
                    ]
    except GPIOError as e:
      print("Unable to access GPIO pins. Did you run with sudo ?")
      sys.exit(1)

    super(UI_EdgeTpuDevBoard, self).__init__()

  def __del__(self):
    if hasattr(self, "_LEDs"):
      for x in self._LEDs or [] + self._buttons or []: x.close()

  def setLED(self, index, state):
    """Abstracts away mix of GPIO and PWM LEDs."""
    if isinstance(self._LEDs[index], GPIO): self._LEDs[index].write(state)
    else: self._LEDs[index].duty_cycle = 1.0 if state else 0.0

  def getButtonState(self):
    return [not button.read() for button in self._buttons]


if __name__== "__main__":
  ui = UI_EdgeTpuDevBoard()
  ui.wiggleLEDs()
  ui.testButtons(1000)

