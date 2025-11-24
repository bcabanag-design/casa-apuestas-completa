import sqlite3
import os

class CasaDeApuestas:
    
    def __init__(self, db_name):
        # Permite acceder a las columnas por nombre
        self.conexion = sqlite3.connect(db_name) 
        self.conexion.row_factory = sqlite3.Row 
        self.cursor = self.conexion.cursor()
        self.crear_tablas() 

    def cerrar_conexion(self):
        """Cierra la conexión con la base de datos."""
        self.conexion.close()
        
    def crear_tablas(self):
        """Método para crear las tablas si no existen."""
        
        # 1. Tabla de Apostadores
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS apostadores (
                nombre TEXT PRIMARY KEY,
                saldo REAL DEFAULT 0.0
            )
        """)
        
        # 2. Tabla de Partidas Abiertas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_equipo1 TEXT NOT NULL,
                nombre_equipo2 TEXT NOT NULL,
                total_apostado_e1 REAL DEFAULT 0.0,
                total_apostado_e2 REAL DEFAULT 0.0,
                equipo_ganador INTEGER, -- 1 o 2
                estado TEXT DEFAULT 'Abierta', -- 'Abierta', 'Resuelta'
                ganancia_casa REAL DEFAULT 0.0
            )
        """)
        
        # 3. Tabla de Apuestas Abiertas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS apuestas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partida_id INTEGER,
                nombre_apostador TEXT,
                monto REAL NOT NULL,
                equipo_apostado INTEGER, -- 1 o 2
                FOREIGN KEY(partida_id) REFERENCES partidas(id),
                FOREIGN KEY(nombre_apostador) REFERENCES apostadores(nombre)
            )
        """)
        
        # 4. TABLA NUEVA: Historial de Apuestas RESUELTAS
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS apuestas_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partida_id INTEGER,
                equipo1 TEXT,
                equipo2 TEXT,
                apostador TEXT,
                monto_apostado REAL NOT NULL,
                monto_cobrado REAL DEFAULT 0.0, -- El pago total recibido (incluyendo la devolución de lo apostado)
                equipo_apostado INTEGER,
                equipo_ganador INTEGER -- 1 o 2
            )
        """)

        self.conexion.commit()

    # --- MÉTODOS EXISTENTES ---
    
    def obtener_apostadores(self):
        self.cursor.execute("SELECT * FROM apostadores")
        return self.cursor.fetchall()
        
    def registrar_apostador(self, nombre, saldo):
        self.cursor.execute("INSERT INTO apostadores (nombre, saldo) VALUES (?, ?)", (nombre, saldo))
        self.conexion.commit()

    def ajustar_saldo_apostador(self, nombre, monto):
        self.cursor.execute("UPDATE apostadores SET saldo = saldo + ? WHERE nombre = ?", (monto, nombre))
        if self.cursor.rowcount == 0:
            raise ValueError(f"Apostador '{nombre}' no encontrado.")
        self.conexion.commit()
    
    def crear_partida(self, equipo1, equipo2):
        self.cursor.execute("INSERT INTO partidas (nombre_equipo1, nombre_equipo2) VALUES (?, ?)", (equipo1, equipo2))
        self.conexion.commit()
        return self.cursor.lastrowid # Devolvemos el ID de la partida

    def obtener_partidas_abiertas(self):
        self.cursor.execute("SELECT * FROM partidas WHERE estado = 'Abierta'")
        return self.cursor.fetchall()

    def obtener_partidas_resueltas(self):
        # Esta función ahora devuelve las partidas de la tabla principal
        self.cursor.execute("SELECT * FROM partidas WHERE estado = 'Resuelta'")
        return self.cursor.fetchall()

    def obtener_apuestas_partida(self, partida_id):
        self.cursor.execute("SELECT * FROM apuestas WHERE partida_id = ?", (partida_id,))
        return self.cursor.fetchall()

    def registrar_apuesta(self, partida_id, nombre_apostador, monto, equipo):
        # 1. Verificar saldo
        self.cursor.execute("SELECT saldo FROM apostadores WHERE nombre = ?", (nombre_apostador,))
        apostador = self.cursor.fetchone()
        if not apostador:
            raise ValueError(f"Apostador '{nombre_apostador}' no encontrado.")
        if apostador['saldo'] < monto:
            raise ValueError(f"Saldo insuficiente para '{nombre_apostador}'. Saldo actual: S/{apostador['saldo']:.2f}")

        # 2. Registrar apuesta
        self.cursor.execute("INSERT INTO apuestas (partida_id, nombre_apostador, monto, equipo_apostado) VALUES (?, ?, ?, ?)", 
                            (partida_id, nombre_apostador, monto, equipo))
        
        # 3. Restar saldo al apostador
        self.cursor.execute("UPDATE apostadores SET saldo = saldo - ? WHERE nombre = ?", (monto, nombre_apostador))
        
        # 4. Actualizar total apostado en la partida
        campo_total = f'total_apostado_e{equipo}'
        self.cursor.execute(f"UPDATE partidas SET {campo_total} = {campo_total} + ? WHERE id = ?", (monto, partida_id))
        
        self.conexion.commit()
    
    # El método borrar_partidas_resueltas ahora borra de ambas tablas (partidas y apuestas_historial)
    def borrar_partidas_resueltas(self):
        """Borra las partidas resueltas de la tabla principal y el historial de apuestas."""
        self.cursor.execute("DELETE FROM apuestas_historial WHERE partida_id IN (SELECT id FROM partidas WHERE estado = 'Resuelta')")
        self.cursor.execute("DELETE FROM partidas WHERE estado = 'Resuelta'")
        self.conexion.commit()

    def calcular_rentabilidad_total(self):
        """Suma todas las comisiones de partidas resueltas."""
        self.cursor.execute("SELECT SUM(ganancia_casa) AS total_ganancia FROM partidas WHERE estado = 'Resuelta'")
        resultado = self.cursor.fetchone()
        return resultado['total_ganancia'] if resultado and resultado['total_ganancia'] is not None else 0.0
        
    def obtener_reporte_partidas(self):
        """Obtiene datos de partidas resueltas para el reporte (usando la tabla principal)."""
        self.cursor.execute("SELECT id, nombre_equipo1, nombre_equipo2, equipo_ganador, ganancia_casa FROM partidas WHERE estado = 'Resuelta'")
        return self.cursor.fetchall()

    # --- MÉTODOS DE RESOLUCIÓN (MODIFICADO para HISTORIAL) ---
    def resolver_partida(self, partida_id, equipo_ganador):
        
        self.cursor.execute("SELECT nombre_equipo1, nombre_equipo2, total_apostado_e1, total_apostado_e2 FROM partidas WHERE id = ?", (partida_id,))
        partida = self.cursor.fetchone()
        
        if not partida:
            raise ValueError("Partida no encontrada.")
            
        nombre_e1 = partida['nombre_equipo1']
        nombre_e2 = partida['nombre_equipo2']
        total_e1 = partida['total_apostado_e1']
        total_e2 = partida['total_apostado_e2']

        # Verificación de montos desiguales
        if total_e1 != total_e2:
             print(f"\n[AVISO] Partida {partida_id}: Montos desiguales. E1: S/{total_e1:.2f}, E2: S/{total_e2:.2f}. Calculando igual...")

        if equipo_ganador == 1:
            total_apostado_perdedor = total_e2 
            total_apostado_ganador = total_e1
            equipo_perdedor = 2
        else: # equipo_ganador == 2
            total_apostado_perdedor = total_e1
            total_apostado_ganador = total_e2
            equipo_perdedor = 1

        COMISION_CASA_PCT = 0.25
        ganancia_casa = total_apostado_perdedor * COMISION_CASA_PCT 
        
        COMISION_GANADORES_PCT = 0.75
        ganancia_para_ganadores = total_apostado_perdedor * COMISION_GANADORES_PCT
        monto_total_a_repartir = total_apostado_ganador + ganancia_para_ganadores

        # 1. Procesar Apuestas Ganadoras
        self.cursor.execute("SELECT nombre_apostador, monto FROM apuestas WHERE partida_id = ? AND equipo_apostado = ?", (partida_id, equipo_ganador))
        apuestas_ganadoras = self.cursor.fetchall()
        
        if total_apostado_ganador > 0:
            for apuesta in apuestas_ganadoras:
                proporcion = apuesta['monto'] / total_apostado_ganador
                pago_total = proporcion * monto_total_a_repartir
                
                # Actualizar saldo del apostador
                self.cursor.execute("UPDATE apostadores SET saldo = saldo + ? WHERE nombre = ?", (pago_total, apuesta['nombre_apostador']))
                
                # *** REGISTRAR EN HISTORIAL ***
                self.cursor.execute("""
                    INSERT INTO apuestas_historial (partida_id, equipo1, equipo2, apostador, monto_apostado, monto_cobrado, equipo_apostado, equipo_ganador)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (partida_id, nombre_e1, nombre_e2, apuesta['nombre_apostador'], apuesta['monto'], pago_total, equipo_ganador, equipo_ganador))


        # 2. Procesar Apuestas Perdedoras (monto_cobrado = 0)
        self.cursor.execute("SELECT nombre_apostador, monto FROM apuestas WHERE partida_id = ? AND equipo_apostado = ?", (partida_id, equipo_perdedor))
        apuestas_perdedoras = self.cursor.fetchall()

        for apuesta in apuestas_perdedoras:
            # *** REGISTRAR EN HISTORIAL ***
            self.cursor.execute("""
                INSERT INTO apuestas_historial (partida_id, equipo1, equipo2, apostador, monto_apostado, monto_cobrado, equipo_apostado, equipo_ganador)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (partida_id, nombre_e1, nombre_e2, apuesta['nombre_apostador'], apuesta['monto'], 0.0, equipo_perdedor, equipo_ganador))


        # 3. Actualizar partida a "Resuelta"
        self.cursor.execute("""
            UPDATE partidas SET 
            equipo_ganador = ?, 
            estado = 'Resuelta', 
            ganancia_casa = ?  
            WHERE id = ?
        """, (equipo_ganador, ganancia_casa, partida_id))

        # 4. Limpiar apuestas abiertas
        self.cursor.execute("DELETE FROM apuestas WHERE partida_id = ?", (partida_id,))
        
        self.conexion.commit() 
        return ganancia_casa
    
    # --- MÉTODOS NUEVOS DE REPORTE ---

    def obtener_balance_apostadores(self):
        """
        Calcula el saldo consolidado y la actividad (apostado, retornado, neto) por apostador.
        Alimenta el primer cuadro del reporte.
        """
        balance = []
        
        # 1. Obtener la lista de todos los apostadores con su saldo actual
        apostadores_db = self.cursor.execute('SELECT nombre, saldo FROM apostadores').fetchall()
        
        for apostador in apostadores_db:
            nombre = apostador['nombre']
            saldo_final = apostador['saldo']
            
            # Calcular actividad desde apuestas_historial
            
            # Total Apostado (lo que él puso en las apuestas resueltas)
            total_apostado_sql = self.cursor.execute(
                "SELECT SUM(monto_apostado) FROM apuestas_historial WHERE apostador = ?",
                (nombre,)
            ).fetchone()[0] or 0.0
            
            # Total Retornado (lo que le pagó la casa por las apuestas resueltas)
            total_retornado_sql = self.cursor.execute(
                "SELECT SUM(monto_cobrado) FROM apuestas_historial WHERE apostador = ?",
                (nombre,)
            ).fetchone()[0] or 0.0
            
            # Ganancia/Pérdida Neta del jugador (Retornado - Apostado)
            ganancia_neta = total_retornado_sql - total_apostado_sql
            
            balance.append({
                'nombre': nombre,
                # El saldo final ya está en la tabla de apostadores y es el valor actual
                'saldo_final': saldo_final, 
                'total_apostado': total_apostado_sql,
                'total_ganado': total_retornado_sql, # Lo renombro a total_ganado para ser más claro
                'ganancia_neta': ganancia_neta
            })
            
        return balance

    def obtener_reporte_apuestas_detallado(self):
        """
        Obtiene el detalle de cada apuesta resuelta desde apuestas_historial.
        Alimenta el último cuadro del reporte y la exportación.
        """
        reporte = []
        try:
            # Obtener el historial completo de apuestas resueltas
            apuestas_db = self.cursor.execute(
                "SELECT * FROM apuestas_historial ORDER BY partida_id DESC"
            ).fetchall()
            
            for apuesta in apuestas_db:
                monto_cobrado = apuesta['monto_cobrado'] or 0.0
                monto_apostado = apuesta['monto_apostado'] or 0.0
                ganancia_neta_apuesta = monto_cobrado - monto_apostado
                
                # Determinar el resultado en texto
                if apuesta['equipo_apostado'] == apuesta['equipo_ganador']:
                    resultado_texto = "Ganada"
                else:
                    resultado_texto = "Perdida"
                
                # Nombre de la partida
                partida_nombre = f"{apuesta['equipo1']} vs {apuesta['equipo2']}"
                
                # Nombre del equipo apostado (más descriptivo)
                equipo_apostado_nombre = apuesta['equipo1'] if apuesta['equipo_apostado'] == 1 else apuesta['equipo2']
                
                reporte.append({
                    'partida_id': apuesta['partida_id'],
                    'apostador': apuesta['apostador'],
                    'partida_nombre': partida_nombre,
                    'equipo_apostado_num': apuesta['equipo_apostado'],
                    'equipo_apostado_nombre': equipo_apostado_nombre,
                    'resultado_texto': resultado_texto,
                    'monto_apostado': monto_apostado,
                    'monto_cobrado': monto_cobrado,
                    'ganancia_neta': ganancia_neta_apuesta
                })
                
        except Exception as e:
            print(f"Error en obtener_reporte_apuestas_detallado: {e}")
            reporte = []
            
        return reporte

# --- SCRIPT DE PRUEBA Y DEMOSTRACIÓN ---
if __name__ == "__main__":
    DB_NAME = 'casa_apuestas.db'

    # ----------------------------------------------------------------------
    # CORRECCIÓN: Comentamos la línea de borrado para que el archivo persista
    # entre ejecuciones. Si quieres un inicio limpio, descomenta esta línea.
    # if os.path.exists(DB_NAME):
    #     os.remove(DB_NAME)
    # ----------------------------------------------------------------------

    print(f"--- INICIANDO DEMOSTRACIÓN ---")
    print(f"Conectando a la base de datos: {DB_NAME}")
    
    try:
        # Inicializar la casa de apuestas
        casa = CasaDeApuestas(DB_NAME)

        # 1. Registrar Apostadores y cargar saldo
        print("\n1. REGISTRANDO APOSTADORES")
        casa.registrar_apostador("Juan", 0.0)
        casa.registrar_apostador("Maria", 0.0)
        # Ajustar saldo solo si se acaban de registrar o es la primera ejecución
        apostadores_iniciales = casa.obtener_apostadores()
        
        # Este chequeo evita agregar saldo cada vez que se corre el script
        if all(a['saldo'] == 0.0 for a in apostadores_iniciales):
            casa.ajustar_saldo_apostador("Juan", 150.0)
            casa.ajustar_saldo_apostador("Maria", 100.0)
        
        apostadores = casa.obtener_apostadores()
        for a in apostadores:
            print(f" - {a['nombre']}: Saldo S/{a['saldo']:.2f}")

        # 2. Crear Partida (Solo si no hay partidas abiertas)
        if not casa.obtener_partidas_abiertas():
            print("\n2. CREANDO PARTIDA")
            partida_id = casa.crear_partida("Leones", "Tigres")
            print(f" - Partida creada (ID {partida_id}): Leones vs Tigres")
            
            # 3. Registrar Apuestas
            print("\n3. REGISTRANDO APUESTAS")
            try:
                casa.registrar_apuesta(partida_id, "Juan", 80.0, 1) # Juan apuesta 80 en Leones (E1)
                print(" - Juan apuesta S/80.00 en Leones")
                casa.registrar_apuesta(partida_id, "Maria", 80.0, 2) # Maria apuesta 80 en Tigres (E2)
                print(" - Maria apuesta S/80.00 en Tigres")
            except ValueError as ve:
                print(f" - No se pudieron registrar todas las apuestas: {ve}")
        else:
            print("\n2. Saltando creación y apuestas de la partida, ya existe una abierta.")
            partida_id = casa.obtener_partidas_abiertas()[0]['id']


        print("\nSaldos después de las apuestas:")
        apostadores = casa.obtener_apostadores()
        for a in apostadores:
            print(f" - {a['nombre']}: Saldo S/{a['saldo']:.2f}")
            
        # 4. Resolver Partida (Solo si no está resuelta)
        partidas_abiertas = casa.obtener_partidas_abiertas()
        if partidas_abiertas:
            partida_a_resolver_id = partidas_abiertas[0]['id']
            print(f"\n4. RESOLVIENDO PARTIDA ABIERTA (ID {partida_a_resolver_id}) (Gana Leones - Equipo 1)")
            
            # Comprobamos que haya apuestas registradas antes de resolver
            if casa.obtener_apuestas_partida(partida_a_resolver_id):
                ganancia_casa = casa.resolver_partida(partida_a_resolver_id, 1)
                print(f" - Partida {partida_a_resolver_id} Resuelta. Ganancia de la Casa: S/{ganancia_casa:.2f}")
            else:
                 print(f" - Partida {partida_a_resolver_id} no tiene apuestas. No se puede resolver.")
        else:
            print("\n4. No hay partidas abiertas para resolver.")


        # 5. Generar Reportes
        print("\n--- REPORTES FINALES ---")

        # Reporte 1: Balance de Apostadores
        print("\nREPORTE 1: BALANCE DE APOSTADORES (Historial Consolidado y Saldo Actual)")
        balance = casa.obtener_balance_apostadores()
        for b in balance:
            estado_neto = "Ganancia" if b['ganancia_neta'] > 0 else "Pérdida" if b['ganancia_neta'] < 0 else "Cero"
            print(f"|----------------------------------------------------")
            print(f"| Apostador: {b['nombre']}")
            print(f"| Saldo Final: S/{b['saldo_final']:.2f}")
            print(f"| Total Apostado (Historial): S/{b['total_apostado']:.2f}")
            print(f"| Total Cobrado (Historial): S/{b['total_ganado']:.2f}")
            print(f"| GANANCIA NETA JUGADOR: S/{b['ganancia_neta']:.2f} ({estado_neto})")
            print(f"|----------------------------------------------------")
            
        # Reporte 2: Partidas Resueltas y Ganancia de la Casa
        print("\nREPORTE 2: PARTIDAS RESUELTAS")
        partidas_resueltas = casa.obtener_reporte_partidas()
        if partidas_resueltas:
            for p in partidas_resueltas:
                ganador = p['nombre_equipo1'] if p['equipo_ganador'] == 1 else p['nombre_equipo2']
                print(f" - ID {p['id']} ({p['nombre_equipo1']} vs {p['nombre_equipo2']}): Ganador: {ganador}. Comisión Casa: S/{p['ganancia_casa']:.2f}")
        else:
             print(" - No hay partidas resueltas en el historial.")


        # Reporte 3: Rentabilidad Total
        rentabilidad = casa.calcular_rentabilidad_total()
        print(f"\nREPORTE 3: RENTABILIDAD TOTAL DE LA CASA: S/{rentabilidad:.2f}")

        # Reporte 4: Detalle de Apuestas
        print("\nREPORTE 4: DETALLE COMPLETO DEL HISTORIAL DE APUESTAS")
        detalle_apuestas = casa.obtener_reporte_apuestas_detallado()
        if detalle_apuestas:
            for d in detalle_apuestas:
                gan_per = "Ganó" if d['resultado_texto'] == 'Ganada' else "Perdió"
                print(f" - Partida {d['partida_id']} | Apostador: {d['apostador']} ({gan_per})")
                print(f"    -> Partida: {d['partida_nombre']}")
                print(f"    -> Apostado en: Equipo {d['equipo_apostado_num']} ({d['equipo_apostado_nombre']})")
                print(f"    -> Monto Apostado: S/{d['monto_apostado']:.2f} | Monto Cobrado: S/{d['monto_cobrado']:.2f} | Ganancia Neta: S/{d['ganancia_neta']:.2f}")
        else:
            print(" - No hay apuestas resueltas en el historial.")


        # 6. Borrar partidas resueltas
        # Las partidas resueltas permanecen hasta que se borren manualmente o el usuario borre el archivo.
        # print("\n5. BORRANDO PARTIDAS RESUELTAS Y SU HISTORIAL...")
        # casa.borrar_partidas_resueltas()
        
    except ValueError as e:
        print(f"\n[ERROR EN LA LÓGICA]: {e}")
    except Exception as e:
        print(f"\n[ERROR INESPERADO]: {e}")
    finally:
        if 'casa' in locals() and casa.conexion:
            casa.cerrar_conexion()
        print("\n--- DEMOSTRACIÓN FINALIZADA ---")