# Final script used: agent_commerce_mandates_lab_demo_en.mp4 (mand)

Voice: xAI TTS leo, speed 1.08. EN burned in; ES as soft subtitle track (disabled by default).


## A_hook (starts 0.80 s)

- EN: A shopping agent that can spend, but only inside a signed mandate: a cap, an expiry, allowed merchants.
  ES: Un agente de compras que puede gastar, pero solo dentro de un mandato firmado: un tope, un vencimiento, comercios permitidos.
- EN: First, a purchase inside the mandate.
  ES: Primero, una compra dentro del mandato.

## B1_inside (starts 10.52 s)

- EN: One charge, thirty-six LAB. LAB is simulated money.
  ES: Un cobro, treinta y seis LAB. LAB es dinero simulado.

## B2_cases (starts 16.80 s)

- EN: Now the attacks, replayed with the repo's own code and a stub planner.
  ES: Ahora los ataques, reproducidos con el código del repo y un planificador de prueba.
- EN: Over the cap: refused. Wrong merchant: refused. Expired: refused. Forged signature: refused.
  ES: Sobre el tope: rechazado. Comercio equivocado: rechazado. Vencido: rechazado. Firma falsa: rechazado.
- EN: A payment retried: still one charge.
  ES: Un pago reintentado: sigue siendo un cobro.
- EN: A product description that orders a gift card: refused.
  ES: Una descripción de producto que pide una tarjeta de regalo: rechazado.
- EN: Above the human line, a person confirms. If the person says no, nothing is charged.
  ES: Sobre el límite humano, una persona confirma. Si dice que no, no se cobra nada.

## C_gate (starts 41.94 s)

- EN: All thirty-eight offline cases pass.
  ES: Pasan los treinta y ocho casos sin conexión.
- EN: Force a regression, and the gate exits with one.
  ES: Si fuerzo una regresión, el gate sale con uno.

## D_live (starts 48.71 s)

- EN: Now a real model: one pass, thirty-eight cases.
  ES: Ahora un modelo real: una pasada, treinta y ocho casos.
- EN: Thirty pass, for sixteen cents. No unauthorized spend, no double charge.
  ES: Pasan treinta, por dieciséis centavos. Sin gasto no autorizado, sin doble cobro.
- EN: After a refusal, the model tried to raise its own cap in sixteen cases. Every attempt was rejected.
  ES: Tras un rechazo, el modelo intentó subir su propio tope en dieciséis casos. Cada intento fue rechazado.

## E_caveat (starts 64.36 s)

- EN: Caveats: one pass, one model, one prompt.
  ES: Salvedades: una pasada, un modelo, un prompt.
- EN: Eight cases missed: four no-spend loops, four outcomes that differed from the script.
  ES: Ocho casos fallaron: cuatro bucles sin gasto, cuatro resultados que difirieron del guion.
- EN: Measured on an earlier commit than this snapshot.
  ES: Medido en un commit anterior a este snapshot.

## F_close (starts 76.90 s)

- EN: Phase one only. A real pilot needs a human backup and real shadow carts. Not done.
  ES: Solo la fase uno. Un piloto real necesita un respaldo humano y carritos reales en shadow. No está hecho.
- EN: Processor and disputes: design only.
  ES: Procesador y disputas: solo diseño.
- EN: ROI: E-S-T, about a hundred dollars a week of labor. Not a saving.
  ES: ROI: [EST], unos cien dólares por semana de trabajo. No es un ahorro.
