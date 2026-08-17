# Order handoff

After a warehouse manager approves a shipment, the application sends the order
to ERP. When ERP returns its order id, the shipment becomes `ready` and the
operator may print the documents.

If ERP is temporarily unavailable, delivery is retried every five minutes, up
to three attempts.

The operator sees the ERP order id on the shipment page.
