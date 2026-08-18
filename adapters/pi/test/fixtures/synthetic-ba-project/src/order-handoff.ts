export function markDeliveryStarted(shipment: { status: string }): void {
  shipment.status = "ready";
}

export function buildErpRequest(shipmentId: string): { shipmentId: string } {
  return { shipmentId };
}
