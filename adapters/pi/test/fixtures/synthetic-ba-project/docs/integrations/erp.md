# ERP integration

The queue provides at-least-once delivery. A timeout means that the application
does not know whether ERP accepted the request. ERP callbacks contain the local
shipment id and, on success, the ERP order id.

ERP may accept only part of a multi-line order. The current requirements do not
say whether the accepted lines should remain in ERP or be rolled back.
