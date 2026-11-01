FROM matrixdotorg/synapse:v1.161.0

COPY homeserver.yaml.template /oryma/homeserver.yaml.template
COPY docker-entrypoint.sh /oryma/docker-entrypoint.sh

ENTRYPOINT ["/oryma/docker-entrypoint.sh"]
