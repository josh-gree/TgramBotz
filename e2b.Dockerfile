# This Dockerfile documents the sandbox environment for reference.
# The actual template (iit8zs8cy1rw0hu9dxgc) is built via the E2B v2 API
# using scripts/build_template.py, layered on top of owngk1zv1374s7wd8y6f.
#
# Effective environment:
#   FROM TEMPLATE owngk1zv1374s7wd8y6f   (ubuntu 22.04 + opencode pre-installed)
#   USER root
#   RUN <doppler CLI apt install>
#   ENV DOPPLER_TOKEN=<token>
#   USER user
