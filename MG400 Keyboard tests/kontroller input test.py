import pygame
import time

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected.")
    raise SystemExit

controller = pygame.joystick.Joystick(0)
controller.init()

print("Controller:", controller.get_name())
print("Axes:", controller.get_numaxes())
print("Buttons:", controller.get_numbuttons())
print("Hats:", controller.get_numhats())
print()
print("Move sticks and press buttons.")
print("Ctrl+C to quit.")
print()

last_axes = [0.0] * controller.get_numaxes()
last_buttons = [0] * controller.get_numbuttons()

try:
    while True:
        pygame.event.pump()

        # Axes
        for i in range(controller.get_numaxes()):
            value = controller.get_axis(i)

            if abs(value - last_axes[i]) > 0.08:
                if abs(value) > 0.10:
                    print(f"AXIS {i}: {value:+.2f}")

                last_axes[i] = value

        # Buttons
        for i in range(controller.get_numbuttons()):
            value = controller.get_button(i)

            if value != last_buttons[i]:
                print(
                    f"BUTTON {i}: "
                    f"{'PRESSED' if value else 'released'}"
                )

                last_buttons[i] = value

        time.sleep(0.03)

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    pygame.quit()