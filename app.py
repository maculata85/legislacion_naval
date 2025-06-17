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

    random.shuffle(preguntas)
    return preguntas[:min(NUM_PREGUNTAS_EXAMEN, len(preguntas))]

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
    if preguntas is None or vidas is None or dificultad_actual is None:
        flash('La sesión del examen ha expirado o no se ha iniciado. Por favor, comienza de nuevo.', 'warning')
        return redirect(url_for('inicio'))

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

        # --- Lógica de avance a la siguiente pregunta o fin del examen (después de POST) ---
        siguiente_indice = indice_pregunta_actual + 1
        session['indice_pregunta_actual'] = siguiente_indice # Actualizar el índice en la sesión

        # VERIFICACIÓN DE FIN DE EXAMEN DESPUÉS DE PROCESAR LA RESPUESTA
        # Si las vidas son negativas (solo posible en Modo Dios después de un fallo)
        # O si ya no hay más preguntas que mostrar.
        if vidas < 0 or siguiente_indice >= len(preguntas):
            return redirect(url_for('resultado'))
        else:
            return redirect(url_for('mostrar_pregunta'))

    # --- Lógica para mostrar la pregunta actual (si la solicitud es GET) ---
    #
    # Redirigir a 'resultado' SI:
    # 1. Ya no hay más preguntas que mostrar (el índice excede el total de preguntas).
    # 2. Las vidas son 0 o menos Y NO ES EL MODO DIOS en la PRIMERA PREGUNTA.
    #    Es decir, si tienes 0 o menos vidas Y no estás en Modo Dios, O si estás en Modo Dios pero ya avanzaste
    #    más allá de la primera pregunta (lo que significa que ya fallaste).

    if indice_pregunta_actual >= len(preguntas):
        return redirect(url_for('resultado'))
    
    # Esta es la parte crítica para el Modo Dios y otros modos al inicio
    # Si vidas <= 0:
    #   - Si es Modo Dios Y estamos en la primera pregunta (indice_pregunta_actual == 0), NO redirigimos.
    #   - En cualquier otro caso (vidas <= 0 Y no es Modo Dios O es Modo Dios pero ya no es la primera pregunta), redirigimos.
    if vidas <= 0:
        if dificultad_actual == 'dios' and indice_pregunta_actual == 0:
            # Es Modo Dios, 0 vidas, primera pregunta. Permite mostrarla. NO REDIRIGIR.
            pass
        else:
            # Vidas agotadas en otro modo O en Modo Dios pero ya después de la primera pregunta (indicando un fallo previo).
            return redirect(url_for('resultado'))


    # Si llegamos aquí, significa que la sesión es válida y debemos mostrar una pregunta.
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
    dificultad_final = session.get('dificultad') # Recuperamos la dificultad para la evaluación final

    # Limpiar la sesión al finalizar el examen para que no arrastre datos viejos
    session.pop('preguntas', None)
    session.pop('respuestas', None)
    session.pop('vidas', None)
    session.pop('dificultad', None)
    session.pop('indice_pregunta_actual', None)

    # --- Lógica de victoria/derrota específica para Modo Dios ---
    if dificultad_final == 'dios':
        if correctas == NUM_PREGUNTAS_EXAMEN and total == NUM_PREGUNTAS_EXAMEN and vidas >= 0:
            # Si es Modo Dios, todas las 15 preguntas son correctas (100% de acierto) y no se agotaron las vidas.
            # (Vidas >=0 es importante si por alguna razon el Modo Dios queda en 0 vidas y no en -1 si falla).
            mensaje_dios = "¡HAS CONQUISTADO EL MODO DIOS! Eres imparable. 🎉"
            temas = [] # No hay temas a repasar si se ganó el Modo Dios
        else:
            # Falló alguna o no completó las 15 perfectas
            mensaje_dios = "El Modo Dios requiere perfección. Sigue estudiando. 😢"
            # Los temas a repasar ya se calculan con los fallos, así que no se alteran aquí
    else:
        mensaje_dios = None # No hay mensaje especial para otros modos

    return render_template('resultado.html', correctas=correctas, total=total,
                           vidas=vidas, porcentaje=porcentaje, temas=temas,
                           mensaje_dios=mensaje_dios) # Pasamos el mensaje especial

if __name__ == '__main__':
    app.run(debug=True)