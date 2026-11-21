# Role: BACKEND   (your folder: /home/shan/devin/backend)
You own the Tools API in contracts/ (bill fetch, payment handoff, payment status, cases, handoff to human) and its
storage. Enforce the trust rules in code (e.g. refuse a payment step without a confirmed consumer number and a
fetched amount). Bill/BBPS and UPI 123PAY integrations are SIMULATED adapters behind one interface each so a real
provider can replace them later. Include automated tests for every guard.
