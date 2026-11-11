from __future__ import annotations


class ConverterError(Exception):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def user_message(self) -> str:
        if self.hint:
            return f"{self.message}\n\n{self.hint}"
        return self.message


class ValidationError(ConverterError):
    pass


class UnsupportedConversionError(ValidationError):
    pass


class OutputExistsError(ValidationError):
    def __init__(self, target) -> None:
        self.target = target
        super().__init__(
            f"Plik docelowy już istnieje: {target}",
            "Wybierz inną nazwę, zezwól na nadpisanie lub użyj unikalnej nazwy.",
        )


class DependencyError(ConverterError):
    pass


class ConversionFailedError(ConverterError):
    pass
