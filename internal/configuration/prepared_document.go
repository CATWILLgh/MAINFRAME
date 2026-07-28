package configuration

import (
	"fmt"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/jsondocument"
)

func (builder *preparationBuilder) document(
	target domain.Location,
) (jsondocument.Document, error) {
	if document, exists := builder.docs[target]; exists {
		return document, nil
	}
	snapshot, exists := builder.files[target]
	if !exists {
		return jsondocument.Document{}, fmt.Errorf("target snapshot is unavailable")
	}
	raw := snapshot.raw
	if !snapshot.present {
		raw = []byte(`{}`)
	}
	document, err := jsondocument.Parse(raw)
	if err != nil {
		return jsondocument.Document{}, err
	}
	builder.docs[target] = document
	return document, nil
}

func (builder *preparationBuilder) set(
	target domain.Location,
	pointer string,
	raw string,
) error {
	document, err := builder.document(target)
	if err != nil {
		return err
	}
	parsed, err := jsondocument.ParsePointer(pointer)
	if err != nil {
		return err
	}
	updated, err := document.Set(parsed, []byte(raw))
	if err != nil {
		return err
	}
	builder.docs[target] = updated
	builder.touch[target] = true
	return nil
}
