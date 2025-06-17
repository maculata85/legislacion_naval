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
    'dios': 1, # <--- CAMBIO CLAVE: Modo Dios ahora tiene 1 vida.
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

    # --- VERIFICACIÓN CRÍTICA DE FIN DE JUEGO (SIMPLIFICADA PARA MODO DIOS DE 1 VIDA) ---
    # Evalúa si el examen debe terminar EN ESTE MOMENTO

    # 1. Si ya no hay más preguntas para mostrar.
    if indice_pregunta_actual >= len(preguntas):
        return redirect(url_for('resultado'))

    # 2. Si las vidas se han agotado (0 o menos).
    #    Con Modo Dios teniendo 1 vida, si vidas <= 0, significa que se equivocó.
    #    Esta condición ahora es simple y directa para todos los modos si vidas_iniciales > 0.
    if vidas <= 0: 
        return redirect(url_for('resultado'))

    # --- Lógica de procesamiento de respuesta (si la solicitud es POST) ---
    if request.method == 'POST':
        seleccion_opcion_str = request.form.get('opcion')

        if seleccion_opcion_str is None:
            flash('Por favor, selecciona una opción antes de responder.', 'warning')
            return redirect(url_for('mostrar_pregunta'))

        pregunta_respondida_obj = preguntas[indice_pregunta_actual]

        # Obtener el texto de la opción correcta de la pregunta actual para comparación
        respuesta_correcta_texto = pregunta_respondida_obj['opciones'][pregunta_respondida_obj['respuesta_correcta']]

        if seleccion_opcion_str != respuesta_correcta_texto:
            vidas -= 1
            session['vidas'] = vidas
            flash(f'¡Incorrecto! La respuesta correcta era: {respuesta_correcta_texto}', 'error')
        else:
            flash('¡Correcto!', 'success')

        respuestas.append({
            'pregunta': pregunta_respondida_obj['pregunta'],
            'seleccion': seleccion_opcion_str, # Guardar la opción seleccionada como texto
            'correcta': respuesta_correcta_texto,
            'tema': pregunta_respondida_obj['tema'],
            'acertada': seleccion_opcion_str == respuesta_correcta_texto
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
    opciones = list(pregunta_a_mostrar['opciones']) # Asegurarse de que sea una lista modificable
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

    # --- Lógica de victoria/derrota específica para Modo Dios (con 1 vida) ---
    mensaje_dios = None
    if dificultad_final == 'dios':
        # Para "ganar" Modo Dios (con 1 vida): respondió TODAS las preguntas y todas fueron correctas
        if correctas == NUM_PREGUNTAS_EXAMEN and total == NUM_PREGUNTAS_EXAMEN:
            mensaje_dios = "¡HAS CONQUISTADO EL MODO DIOS! Eres imparable. 🎉"
            temas = [] # No hay temas a repasar si se ganó Modo Dios
        else:
            # Pierde si falló alguna o no completó todas las preguntas
            mensaje_dios = "El Modo Dios con una vida requiere perfección. Sigue estudiando. 😢"

    return render_template('resultado.html', correctas=correctas, total=total,
                           vidas=vidas, porcentaje=porcentaje, temas=temas,
                           mensaje_dios=mensaje_dios)

if __name__ == '__main__':
    app.run(debug=True)