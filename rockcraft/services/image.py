# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Rockcraft Image Service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from craft_application import AppMetadata, BaseService, ServiceFactory
from craft_cli import emit

from rockcraft import models, oci


@dataclass(frozen=True)
class ImageInfo:
    """Metadata about a fetched OCI Image."""

    base_image: oci.Image
    base_layer_dir: Path
    base_digest: bytes


class RockcraftImageService(BaseService):
    """Service to fetch and cache OCI images."""

    def __init__(
        self,
        app: AppMetadata,
        project: models.Project,
        services: ServiceFactory,
        *,
        work_dir: Path,
        build_for: str,
    ):
        super().__init__(app, project, services)

        self._work_dir = work_dir
        self._build_for = build_for
        self._image_info: ImageInfo | None = None

    def obtain_image(self) -> ImageInfo:
        """Return the ImageInfo for the project's base, possibly fetching it."""
        if self._image_info is None:
            self._image_info = self._create_image_info()

        return self._image_info

    def _create_image_info(self) -> ImageInfo:
        image_dir = self._work_dir / "images"
        bundle_dir = self._work_dir / "bundles"
        build_for = self._build_for
        project = cast(models.Project, self._project)
        if project.base == "bare":
            base_image, source_image = oci.Image.new_oci_image(
                f"{project.base}:latest",
                image_dir=image_dir,
                arch=self._build_for,
                variant=None,  # TODO
            )
        else:
            base_image, source_image = oci.Image.from_docker_registry(
                project.base,
                image_dir=image_dir,
                arch=self._build_for,
                variant=None,  # TODO
            )
        emit.progress(f"Retrieved base {project.base} for {build_for}", permanent=True)

        emit.progress(f"Extracting {base_image.image_name}")
        rootfs = base_image.extract_to(bundle_dir)
        emit.progress(f"Extracted {base_image.image_name}", permanent=True)

        # TODO: check if destination image already exists, etc.
        project_base_image = base_image.copy_to(
            f"{project.name}:rockcraft-base", image_dir=image_dir
        )

        base_digest = project_base_image.digest(source_image)

        return ImageInfo(
            base_image=project_base_image,
            base_layer_dir=rootfs,
            base_digest=base_digest,
        )
