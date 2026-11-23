import unittest

from delivery.core.factory import build_app
from delivery.producer.sample_data import load_sample_data

class HealthCheckTestCase(unittest.TestCase):

    def assert_app_is_healthy(self):
        self.assertEqual(self.app.health.problems(), [])
    
    def setUp(self):
        self.app = load_sample_data(build_app())

    def test_initial_application_is_healthy(self):
        self.assert_app_is_healthy()

    def test_new_order_is_healthy(self):
        self.app.order_service.place_order(
            "C1", "R1", [("Pizza", 1)]
        )
        self.assert_app_is_healthy()


    def test_new_order_with_courier_is_reported(self):
        order = self.app.order_service.place_order(
            "C1", "R1", [("Pizza", 1)]
        )
        courier = self.app.couriers.get("K1")
        
        #Unhealthy state
        #NEW ORDER MUST NOT HAVE A COURIER 
        order.set_courier(courier)

        problems = self.app.health.problems()
        self.assertIn(
            f"Order {order.id} is NEW but already has a courier.",
            problems,
        )


if __name__ == "__main__":
    unittest.main()