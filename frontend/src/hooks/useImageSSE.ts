import { useEffect, useRef } from 'react'

interface ImageSSEEvent {
  status:    'pending' | 'completed' | 'failed'
  image_id:  string
  image_url?: string
  error?:    string
}

/**
 * Subscreve ao SSE de status de uma imagem.
 * Chama onCompleted(imageUrl) quando a imagem ficar pronta.
 * Chama onFailed() se falhar ou timeout.
 * imageId = null/undefined desativa o hook.
 */
export function useImageSSE(
  imageId: string | null | undefined,
  onCompleted: (imageUrl: string) => void,
  onFailed?: () => void,
) {
  const onCompletedRef = useRef(onCompleted)
  const onFailedRef    = useRef(onFailed)
  onCompletedRef.current = onCompleted
  onFailedRef.current    = onFailed

  useEffect(() => {
    if (!imageId) return

    const es = new EventSource(`/api/images/${imageId}/stream`)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as ImageSSEEvent
        if (data.status === 'completed' && data.image_url) {
          onCompletedRef.current(data.image_url)
          es.close()
        } else if (data.status === 'failed') {
          onFailedRef.current?.()
          es.close()
        }
      } catch { /* ignora parse errors */ }
    }

    es.onerror = () => {
      onFailedRef.current?.()
      es.close()
    }

    return () => es.close()
  }, [imageId])
}
