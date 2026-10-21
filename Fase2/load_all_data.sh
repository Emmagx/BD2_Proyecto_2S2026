#!/bin/bash
set -e

CONTAINER_NAME="postgres_cali"
DB_NAME="olimpiadas_db"
DB_USER="postgres"

echo "=== Cargando datos completos en PostgreSQL ($CONTAINER_NAME) ==="

docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME << 'EOF'
\copy "PAIS" FROM '/csv-limpios/1_PAIS.csv' WITH (FORMAT csv, HEADER true);
\copy "DEPORTE" FROM '/csv-limpios/2_DEPORTE.csv' WITH (FORMAT csv, HEADER true);
\copy "OLIMPIADA" FROM '/csv-limpios/3_OLIMPIADA.csv' WITH (FORMAT csv, HEADER true);
\copy "MEDALLA" FROM '/csv-limpios/4_MEDALLA.csv' WITH (FORMAT csv, HEADER true);
\copy "REGION" FROM '/csv-limpios/5_REGION.csv' WITH (FORMAT csv, HEADER true);
\copy "DISCIPLINA" FROM '/csv-limpios/6_DISCIPLINA.csv' WITH (FORMAT csv, HEADER true);
\copy "POBLACION" FROM '/csv-limpios/7_POBLACION.csv' WITH (FORMAT csv, HEADER true);
\copy "CIUDAD" FROM '/csv-limpios/8_CIUDAD.csv' WITH (FORMAT csv, HEADER true);
\copy "EVENTO" FROM '/csv-limpios/9_EVENTO.csv' WITH (FORMAT csv, HEADER true);
\copy "ATLETA" FROM '/csv-limpios/10_ATLETA.csv' WITH (FORMAT csv, HEADER true);
\copy "CIUDAD_OLIMPIADA" FROM '/csv-limpios/11_CIUDAD_OLIMPIADA.csv' WITH (FORMAT csv, HEADER true);
--\copy "RESULTADO" FROM '/cargas/12_RESULTADO.csv' WITH (FORMAT csv, HEADER true);
--\copy "RESULTADO_ATLETA" FROM '/cargas/13_RESULTADO_ATLETA.csv' WITH (FORMAT csv, HEADER true);
EOF

echo "=== Carga finalizada con éxito ==="
