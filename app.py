# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash

import random
from base_de_preguntas import BASE_DE_PREGUNTAS

app = Flask(__name__)
app.secret_key = 'clave_secreta_cambia_esto' # ¡IMPORTANTE! Cambia esto por una clave secreta fuerte y única en producción

NUM_PREGUNTAS_EXAMEN = 15

DIFICULTADES = {
    'facil': 3,
    'intermedio': 2,
    'dificil': 1,
    'dios': 0, # Modo Dios: 0 vidas
    'todos': 2
}

def preparar_examen(dificultad):
    """
    Filtra y selecciona las preguntas para el examen según la dificultad.
    """
    if dificultad == 'todos':
        preguntas = BASE_DE_PREGUNTAS[:] # Copia completa si es "todos"
    else:
        preguntas = [p for p in BASE_DE_PREGUNTAS if p['dificultad'] == dificultad]

    # Si no hay suficientes preguntas, se usaran las que haya
    num_a_seleccionar = min(NUM_PREGUNTAS_EXAMEN, len(preguntas))
    random.shuffle(preguntas)
    return preguntas[:num_a_seleccionar]

@app.route('/')
def inicio():
    """
    Ruta para la página de inicio, donde se selecciona la dificultad.
    """
    return render_template('inicio.html')

@app.route('/examen', methods=['POST'])
def examen():
    """
    Ruta para iniciar el examen, procesa la selección de dificultad y prepara la sesión.
    """
    # --- IMPORTANTE: Limpiar la sesión al inicio de un nuevo examen ---
    session.clear() 

    dificultad = request.form['dificultad']
    preguntas = preparar_examen(dificultad)
    vidas = DIFICULTADES[dificultad]

    # Inicializa las variables de sesión para el nuevo examen
    session['preguntas'] = preguntas
    session['respuestas'] = []
    session['vidas'] = vidas
    session['dificultad'] = dificultad
    session['indice_pregunta_actual'] = 0 # Almacena el índice de la pregunta actual

    # Redirige a la primera pregunta
    return redirect(url_for('mostrar_pregunta'))

@app.route('/pregunta', methods=['GET', 'POST'])
def mostrar_pregunta():
    """
    Ruta para mostrar una pregunta y procesar su respuesta.
    """
    preguntas = session.get('preguntas')
    respuestas = session.get('respuestas', [])
    vidas = session.get('vidas')
    dificultad_actual = session.get('dificultad')
    indice_pregunta_actual = session.get('indice_pregunta_actual', 0)

    # --- Validación inicial de sesión para robustez ---
    # Si los datos esenciales de la sesión no están, redirigir al inicio.
    if preguntas is None or vidas is None or dificultad_actual is None:
        flash('La sesión del examen ha expirado o no se ha iniciado. Por favor, comienza de nuevo.', 'warning')
        return redirect(url_for('inicio'))

    # --- VERIFICACIÓN CRÍTICA PARA FIN DE JUEGO (SE EJECUTA EN CADA CARGA GET O DESPUÉS DE UN POST) ---
    # Evalúa si el examen debe terminar EN ESTE MOMENTO

    # 1. Si ya no hay más preguntas para mostrar (el índice actual es igual o mayor al total de preguntas)
    if indice_pregunta_actual >= len(preguntas):
        return redirect(url_for('resultado'))

    # 2. Si las vidas se han agotado (o son negativas)
    #    Excepción: Si es Modo Dios y estamos en la primera pregunta (indice 0), NO se considera fin de juego todavía.
    #    Solo si las vidas son negativas (Modo Dios se equivocó) O si no es Modo Dios y sus vidas llegaron a cero.
    if vidas <= 0: # Si las vidas son 0 o menos
        # Si ES Modo Dios y NO es la primera pregunta (ya avanzó o se equivocó)
        if dificultad_actual == 'dios' and indice_pregunta_actual > 0:
            return redirect(url_for('resultado'))
        # Si ES Modo Dios y sus vidas son negativas (se equivocó en cualquier pregunta)
        elif dificultad_actual == 'dios' and vidas < 0:
            return redirect(url_for('resultado'))
        # Si NO ES Modo Dios y sus vidas llegaron a cero (fin de juego normal)
        elif dificultad_actual != 'dios':
            return redirect(url_for('resultado'))
        # En cualquier otro caso (Modo Dios, 0 vidas, primera pregunta), NO REDIRIGE, permite mostrar la pregunta.


    # --- Lógica de procesamiento de respuesta (si la solicitud es POST) ---
    if request.method == 'POST':
        seleccion = request.form.get('opcion')

        if seleccion is None:
            flash('Por favor, selecciona una opción antes de responder.', 'warning')
            return redirect(url_for('mostrar_pregunta'))

        pregunta_respondida_obj = preguntas[indice_pregunta_actual]
        correcta = pregunta_respondida_obj['opciones'][pregunta_respondida_obj['respuesta_correcta']]

        if seleccion != correcta:
            vidas -= 1
            session['vidas'] = vidas
            flash(f'¡Incorrecto! La respuesta correcta era: {correcta}', 'error')
        else:
            flash('¡Correcto!', 'success')

        respuestas.append({
            'pregunta': pregunta_respondida_obj['pregunta'],
            'seleccion': seleccion,
            'correcta': correcta,
            'tema': pregunta_respondida_obj['tema'],
            'acertada': seleccion == correcta
        })
        session['respuestas'] = respuestas

        # --- Lógica de avance a la siguiente pregunta ---
        session['indice_pregunta_actual'] = indice_pregunta_actual + 1

        # Después de procesar una respuesta (POST), siempre redirigimos a la misma ruta GET
        # para que la lógica de verificación de fin de juego (al inicio de la función GET)
        # se evalúe para la SIGUIENTE pregunta o para determinar si el examen terminó.
        return redirect(url_for('mostrar_pregunta'))

    # --- Lógica para mostrar la pregunta actual (si la solicitud es GET y el examen NO ha terminado) ---
    pregunta_a_mostrar = preguntas[indice_pregunta_actual]
    opciones = pregunta_a_mostrar['opciones'][:]
    random.shuffle(opciones)

    return render_template('examen.html',
                           num=indice_pregunta_actual,
                           total=len(preguntas),
                           pregunta=pregunta_a_mostrar['pregunta'],
                           opciones=opciones,
                           tema=pregunta_a_mostrar['tema'],
                           vidas=vidas,
                           dificultad_actual=dificultad_actual,
                           DIFICULTADES=DIFICULTADES)

@app.route('/resultado')
def resultado():
    """
    Ruta para mostrar los resultados finales del examen.
    """
    respuestas = session.get('respuestas', [])
    vidas = session.get('vidas', 0)
    total = len(respuestas)
    correctas = sum(1 for r in respuestas if r['acertada'])
    temas = sorted(set(r['tema'] for r in respuestas if not r['acertada']))
    porcentaje = (correctas / total) * 100 if total > 0 else 0
    dificultad_final = session.get('dificultad') 

    # Limpiar la sesión al finalizar el examen para que no arrastre datos viejos
    session.pop('preguntas', None)
    session.pop('respuestas', None)
    session.pop('vidas', None)
    session.pop('dificultad', None)
    session.pop('indice_pregunta_actual', None)

    # --- Lógica de victoria/derrota específica para Modo Dios ---
    mensaje_dios = None
    # Si la dificultad era Dios:
    if dificultad_final == 'dios':
        # Gana si: respondió TODAS las preguntas Y todas fueron correctas Y las vidas NO son negativas (nunca cometió un error).
        if correctas == NUM_PREGUNTAS_EXAMEN and total == NUM_PREGUNTAS_EXAMEN and vidas >= 0:
            mensaje_dios = "¡HAS CONQUISTADO EL MODO DIOS! Eres imparable. 🎉"
            temas = [] # Si se ganó Modo Dios, no hay temas a repasar
        else:
            # Pierde si: no respondió todas correctamente O si las vidas se volvieron negativas.
            mensaje_dios = "El Modo Dios requiere perfección. Sigue estudiando. 😢"

    return render_template('resultado.html', correctas=correctas, total=total,
                           vidas=vidas, porcentaje=porcentaje, temas=temas,
                           mensaje_dios=mensaje_dios)

if __name__ == '__main__':
    app.run(debug=True)