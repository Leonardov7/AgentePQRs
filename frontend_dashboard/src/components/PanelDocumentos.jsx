import React, { useState, useEffect, useRef, useCallback } from 'react';

// Panel "Documentos adicionales" (PDF y Word).
// Los documentos viven en el mismo dataset de Dify que la base del sitio web, con el prefijo DOC__,
// por eso una actualización del sitio nunca los borra.
// Estilos: GestionConocimiento.css (clases gc-*), importado por la pantalla que contiene este panel.

const API = 'http://localhost:8000/api/v1/admin/conocimiento/documentos';

const estadoVisible = (estado) => {
  if (estado === 'completed') return { texto: 'Listo', clase: 'gc-chip--ok' };
  if (estado === 'error') return { texto: 'Con error', clase: 'gc-chip--error' };
  return { texto: 'Procesando', clase: 'gc-chip--proceso' };
};

const PanelDocumentos = ({ onAviso }) => {
  const [documentos, setDocumentos] = useState([]);
  const [errorLista, setErrorLista] = useState('');
  const [cargandoLista, setCargandoLista] = useState(true);
  const [archivo, setArchivo] = useState(null);
  const [titulo, setTitulo] = useState('');
  const [vista, setVista] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [modalVista, setModalVista] = useState(false);
  const [confirmacion, setConfirmacion] = useState(null);   // { tipo: 'eliminar' | 'reemplazar', doc, archivo? }
  const [reemplazandoId, setReemplazandoId] = useState(null);
  const entradaArchivo = useRef(null);
  const entradaReemplazo = useRef(null);

  const avisar = (tipo, texto) => { if (onAviso) onAviso(tipo, texto); };

  const cargarLista = useCallback(async () => {
    try {
      const res = await fetch(API);
      const datos = await res.json();
      if (!res.ok) throw new Error(datos.detail || 'No se pudo consultar la base de conocimiento.');
      setDocumentos(datos.documentos || []);
      setErrorLista('');
    } catch (e) {
      setErrorLista(e.message || 'Sin conexión con el servidor.');
    } finally {
      setCargandoLista(false);
    }
  }, []);

  useEffect(() => { cargarLista(); }, [cargarLista]);

  // Mientras algún documento se esté procesando, se refresca solo
  useEffect(() => {
    const pendiente = documentos.some((d) => d.estado !== 'completed' && d.estado !== 'error');
    if (!pendiente) return undefined;
    const t = setInterval(cargarLista, 4000);
    return () => clearInterval(t);
  }, [documentos, cargarLista]);

  const detalleError = async (res) => {
    try { return (await res.json()).detail || `Error ${res.status}`; } catch { return `Error ${res.status}`; }
  };

  const formulario = (f, t) => {
    const fd = new FormData();
    fd.append('archivo', f);
    if (t) fd.append('titulo', t);
    return fd;
  };

  const elegirArchivo = (e) => {
    const f = e.target.files && e.target.files[0];
    setArchivo(f || null);
    setVista(null);
    if (f) setTitulo(f.name.replace(/\.(pdf|docx)$/i, '').replace(/_/g, ' ').trim());
  };

  const previsualizar = async () => {
    if (!archivo || !titulo.trim()) return;
    setOcupado(true);
    try {
      const res = await fetch(`${API}/previsualizar`, { method: 'POST', body: formulario(archivo, titulo.trim()) });
      if (!res.ok) throw new Error(await detalleError(res));
      setVista(await res.json());
      setModalVista(true);
    } catch (e) {
      avisar('error', e.message);
    } finally { setOcupado(false); }
  };

  const agregar = async () => {
    setOcupado(true);
    try {
      const res = await fetch(API, { method: 'POST', body: formulario(archivo, titulo.trim()) });
      if (!res.ok) throw new Error(await detalleError(res));
      const datos = await res.json();
      avisar('ok', `«${datos.nombre}» se agregó a la base de conocimiento (${datos.fragmentos} fragmentos). Estará disponible en unos segundos.`);
      setArchivo(null); setTitulo(''); setVista(null); setModalVista(false);
      if (entradaArchivo.current) entradaArchivo.current.value = '';
      cargarLista();
    } catch (e) {
      avisar('error', e.message);
      setModalVista(false);
    } finally { setOcupado(false); }
  };

  const pedirReemplazo = (doc) => {
    setReemplazandoId(doc.id);
    if (entradaReemplazo.current) {
      entradaReemplazo.current.value = '';
      entradaReemplazo.current.click();
    }
  };

  const archivoParaReemplazo = (e) => {
    const f = e.target.files && e.target.files[0];
    const doc = documentos.find((d) => d.id === reemplazandoId);
    if (f && doc) setConfirmacion({ tipo: 'reemplazar', doc, archivo: f });
  };

  const confirmar = async () => {
    if (!confirmacion) return;
    const { tipo, doc, archivo: nuevo } = confirmacion;
    setOcupado(true);
    try {
      if (tipo === 'eliminar') {
        const res = await fetch(`${API}/${doc.id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(await detalleError(res));
        avisar('ok', `«${doc.nombre}» se eliminó de la base de conocimiento.`);
      } else {
        const res = await fetch(`${API}/${doc.id}`, { method: 'PUT', body: formulario(nuevo, doc.nombre) });
        if (!res.ok) throw new Error(await detalleError(res));
        const datos = await res.json();
        avisar('ok', `«${doc.nombre}» se reemplazó correctamente (${datos.fragmentos} fragmentos).`);
      }
      cargarLista();
    } catch (e) {
      avisar('error', e.message);
    } finally { setOcupado(false); setConfirmacion(null); setReemplazandoId(null); }
  };

  return (
    <div className="gc-card gc-documentos">
      <div className="gc-card-head">
        <h3>Documentos adicionales</h3>
        <p>
          Información que no está en el sitio web, como reglamentos, manuales o políticas (PDF o Word).
          Se suma a la base del sitio y se conserva aunque el sitio se actualice.
        </p>
      </div>

      {/* ---------- Agregar ---------- */}
      <div className="gc-subida">
        <div className="gc-campo">
          <label>1. Archivo (PDF o Word, hasta 25 MB)</label>
          <div className="gc-archivo">
            <label className="gc-btn gc-btn--secundario">
              Seleccionar archivo
              <input ref={entradaArchivo} type="file" accept=".pdf,.docx" onChange={elegirArchivo} disabled={ocupado} />
            </label>
            <span title={archivo ? archivo.name : ''}>{archivo ? archivo.name : 'Ningún archivo seleccionado'}</span>
          </div>
        </div>
        <div className="gc-campo">
          <label htmlFor="gc-nombre-doc">2. Nombre del documento</label>
          <input id="gc-nombre-doc" type="text" value={titulo} onChange={(e) => { setTitulo(e.target.value); setVista(null); }}
            disabled={ocupado || !archivo} placeholder="Ej: Reglamento Estudiantil" />
        </div>
        <div>
          <button className="gc-btn" onClick={previsualizar} disabled={!archivo || !titulo.trim() || ocupado}>
            {ocupado && !modalVista && !confirmacion ? 'Procesando…' : '3. Ver vista previa'}
          </button>
        </div>
      </div>

      {/* ---------- Lista ---------- */}
      <div className="gc-subtitulo">Documentos cargados ({documentos.length})</div>
      {errorLista ? (
        <div className="gc-aviso gc-aviso--error" style={{ marginTop: '0.5rem' }}>{errorLista}</div>
      ) : cargandoLista ? (
        <div className="gc-vacio">Consultando documentos…</div>
      ) : documentos.length === 0 ? (
        <div className="gc-vacio">Todavía no hay documentos adicionales.</div>
      ) : (
        <div className="gc-tabla-wrap">
          <table className="gc-tabla">
            <thead>
              <tr><th>Documento</th><th>Estado</th><th>Palabras</th><th>Fecha</th><th style={{ textAlign: 'right' }}>Acciones</th></tr>
            </thead>
            <tbody>
              {documentos.map((d) => {
                const est = estadoVisible(d.estado);
                return (
                  <tr key={d.id}>
                    <td className="gc-nombre">{d.nombre}</td>
                    <td><span className={`gc-chip ${est.clase}`}><i />{est.texto}</span></td>
                    <td>{d.palabras != null ? d.palabras.toLocaleString() : '—'}</td>
                    <td>{d.creado ? new Date(d.creado * 1000).toLocaleDateString() : '—'}</td>
                    <td className="gc-acciones">
                      <button className="gc-btn gc-btn--sm gc-btn--secundario" disabled={ocupado} onClick={() => pedirReemplazo(d)}>Reemplazar</button>
                      <button className="gc-btn gc-btn--sm gc-btn--peligro" disabled={ocupado} onClick={() => setConfirmacion({ tipo: 'eliminar', doc: d })}>Eliminar</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <input ref={entradaReemplazo} type="file" accept=".pdf,.docx" onChange={archivoParaReemplazo} style={{ display: 'none' }} />

      {/* ---------- Ventana: vista previa ---------- */}
      {modalVista && vista && (
        <div className="modal-overlay">
          <div className="modal-content gc-modal">
            <div className="modal-header">
              <h3>Vista previa: {vista.nombre}</h3>
              <button className="modal-close-btn" onClick={() => setModalVista(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="gc-datos">
                <span><strong>Formato:</strong> {vista.tipo.toUpperCase()}</span>
                {vista.paginas ? <span><strong>Páginas:</strong> {vista.paginas}</span> : null}
                <span><strong>Caracteres:</strong> {vista.caracteres.toLocaleString()}</span>
                <span><strong>Fragmentos:</strong> {vista.fragmentos}</span>
              </div>
              {(vista.advertencias || []).map((a, i) => <div key={i} className="gc-alerta">{a}</div>)}
              <p className="gc-nota" style={{ marginTop: 0 }}>
                Así verá el asistente los primeros {(vista.muestra || []).length} fragmentos. Revisa que el texto esté completo y en orden.
              </p>
              {(vista.muestra || []).map((f, i) => <pre key={i} className="gc-fragmento">{f}</pre>)}
              {vista.fragmentos > (vista.muestra || []).length && (
                <p className="gc-nota">… y {vista.fragmentos - vista.muestra.length} fragmentos más.</p>
              )}
            </div>
            <div className="gc-modal-pie">
              <button className="gc-btn gc-btn--secundario" onClick={() => setModalVista(false)} disabled={ocupado}>Cancelar</button>
              <button className="gc-btn" onClick={agregar} disabled={ocupado}>{ocupado ? 'Enviando…' : 'Agregar a la base'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ---------- Ventana: confirmación ---------- */}
      {confirmacion && (
        <div className="modal-overlay">
          <div className="modal-content gc-modal gc-modal--chico">
            <div className="modal-header">
              <h3>{confirmacion.tipo === 'eliminar' ? 'Eliminar documento' : 'Reemplazar documento'}</h3>
              <button className="modal-close-btn" onClick={() => { setConfirmacion(null); setReemplazandoId(null); }}>✕</button>
            </div>
            <div className="modal-body" style={{ background: '#fff' }}>
              {confirmacion.tipo === 'eliminar' ? (
                <p style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  ¿Eliminar <strong>«{confirmacion.doc.nombre}»</strong>? El asistente dejará de usar su contenido.
                </p>
              ) : (
                <p style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>
                  ¿Reemplazar el contenido de <strong>«{confirmacion.doc.nombre}»</strong> con el archivo{' '}
                  <strong>{confirmacion.archivo.name}</strong>?
                </p>
              )}
            </div>
            <div className="gc-modal-pie">
              <button className="gc-btn gc-btn--secundario" onClick={() => { setConfirmacion(null); setReemplazandoId(null); }} disabled={ocupado}>Cancelar</button>
              {confirmacion.tipo === 'eliminar'
                ? <button className="gc-btn" style={{ background: '#b42318', borderColor: '#b42318' }} onClick={confirmar} disabled={ocupado}>{ocupado ? 'Eliminando…' : 'Eliminar'}</button>
                : <button className="gc-btn" onClick={confirmar} disabled={ocupado}>{ocupado ? 'Reemplazando…' : 'Reemplazar'}</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PanelDocumentos;